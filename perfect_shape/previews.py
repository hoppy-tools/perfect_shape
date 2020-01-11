import atexit
import bpy
import bgl
import gpu

from bpy.utils import previews
from mathutils import Matrix, Color
from gpu_extras.batch import batch_for_shader


PREVIEW_WIDTH = 512
PREVIEW_HEIGHT = 512

PREVIEW_MAX_POINTS = 128

preview_collections = {}

point_shader = None
line_shader = None

point_vertex_shader = '''
    uniform mat4 ModelViewProjectionMatrix;

    in vec2 position;
    in vec4 color;
    
    out vec4 col;
    out mat4 proj_mat;

    void main()
    {
        gl_PointSize = 20.0;
        gl_Position = ModelViewProjectionMatrix * vec4(position, 0.0, 1.0);
        
        col = color;
        proj_mat = ModelViewProjectionMatrix;
    }
'''

point_fragment_shader = '''
    in vec4 col;
    in mat4 proj_mat;
    
    uniform vec2 holes[{PREVIEW_MAX_POINTS}];
    uniform int holes_count;
    uniform vec2 resolution;
    
    void main(void) {
        for (int i = 0; i < holes_count; i++)
        {
            if(distance((proj_mat * vec4(holes[i], 0.0, 1.0)).xy, (gl_FragCoord.xy / resolution - 0.5) * 2 ) < 0.025) {
                discard;
            }
        }
        
        vec2 circCoord = 2.0 * gl_PointCoord - 1.0;
        float radius = dot(circCoord, circCoord);
    
        vec3 ambient = col.xyz;
        const vec3 lightDiffuse = vec3(0.3, 0.3, 0.3);
    
        vec3 normal = vec3(circCoord, sqrt(1.0 - radius));
        vec3 lightDir = normalize(vec3(0, -1, -0.5));
        float color = max(dot(normal, lightDir), 0.0);
    
        float delta = fwidth(radius);        
        float alpha = 1.0 - smoothstep(0.9 - delta, 0.9 + delta, radius);
        if(alpha == 1.0)
            alpha = alpha - smoothstep(0.4 + delta, 0.4 - delta, radius);
    
        gl_FragColor = vec4(ambient + lightDiffuse * color, alpha - (1.0-col.w));
    }
'''
point_fragment_shader = point_fragment_shader.replace('{PREVIEW_MAX_POINTS}', str(PREVIEW_MAX_POINTS*2))

line_vertex_shader = '''
    uniform mat4 ModelViewProjectionMatrix;

    in vec2 position;
    out mat4 proj_mat;

    void main(void)
    {
        proj_mat = ModelViewProjectionMatrix;
        gl_Position = proj_mat * vec4(position, 0.0, 1.0);
    };
'''

line_fragment_shader = '''
    uniform vec4 color;
    uniform vec2 points[{PREVIEW_MAX_POINTS}];
    uniform int points_count;
    uniform vec2 resolution;
    
    in mat4 proj_mat;
    
    void main(void)
    {
        for (int i = 0; i < points_count; i++)
        {
            if(distance((proj_mat * vec4(points[i], 0.0, 1.0)).xy, (gl_FragCoord.xy / resolution - 0.5) * 2 ) < 0.025) {
                discard;
            }
        }
        
        gl_FragColor = color;        
    };
'''
line_fragment_shader = line_fragment_shader.replace('{PREVIEW_MAX_POINTS}', str(PREVIEW_MAX_POINTS*2))


def get_preview(collection_name, preview_name):
    pcoll = preview_collections[collection_name]
    if preview_name in pcoll:
        preview = pcoll.get(preview_name)
    else:
        preview = pcoll.new(preview_name)
        preview.image_size = (PREVIEW_WIDTH, PREVIEW_HEIGHT)
    return preview


def get_shape_preview_icon_id(preview_name):
    return get_preview('shape_types', preview_name).icon_id


def get_active_color(alpha=1.0):
    return (*bpy.context.preferences.themes[0].view_3d.vertex_select, alpha)


def get_inactive_color(alpha=1.0):
    color = get_active_color(alpha)
    color = Color(color[:3])
    color.s = 0.2
    color.v = 0.6
    return (*color, alpha)


def get_points_colors(points_count, original_count):
    active_color = get_active_color()
    inactive_color = get_inactive_color()

    return [active_color if i < original_count else inactive_color for i in range(points_count)]


def render(shape, rotation=None):
    points = shape.get_points()
    points_original = shape.get_points_original()
    points_count = shape.get_points_count()

    point_batch = batch_for_shader(point_shader, 'POINTS',
                                   {"position": points,
                                    "color": get_points_colors(points_count, points_count)})
    line_batch = batch_for_shader(line_shader, 'LINE_LOOP', {"position": points})

    original_point_batch = batch_for_shader(point_shader, 'POINTS',
                                            {"position": points_original,
                                             "color": get_points_colors(len(points_original), 0)})
    original_line_batch = batch_for_shader(line_shader, 'LINE_LOOP', {"position": points_original})

    offscreen = gpu.types.GPUOffScreen(PREVIEW_WIDTH, PREVIEW_HEIGHT)
    with offscreen.bind():
        bgl.glEnable(bgl.GL_PROGRAM_POINT_SIZE)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

        projection_matrix = Matrix.Identity(4) @ Matrix.Scale(0.8, 4)
        if rotation:
            projection_matrix = projection_matrix @ Matrix.Rotation(-rotation, 4, 'Z')
        original_projection_matrix = Matrix.Identity(4) @ Matrix.Scale(0.8, 4)
        if rotation:
            original_projection_matrix = original_projection_matrix @ Matrix.Rotation(-rotation, 4, 'Z')
        with gpu.matrix.push_pop():

            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(projection_matrix)

            bgl.glLineWidth(4.0)
            bgl.glEnable(bgl.GL_LINE_SMOOTH)
            line_shader.bind()
            line_shader.uniform_float("resolution", (PREVIEW_WIDTH, PREVIEW_HEIGHT))

            if points_original:
                holes = points + points_original
                gpu.matrix.load_projection_matrix(original_projection_matrix)
            else:
                holes = points_original

            if original_line_batch:
                line_shader.uniform_int("points_count", len(holes))
                for i, c in enumerate(holes):
                    line_shader.uniform_float("points[{}]".format(i), c)
                line_shader.uniform_float("color", get_inactive_color())
                original_line_batch.draw(line_shader)

            if original_point_batch:
                point_shader.bind()
                point_shader.uniform_float("resolution", (PREVIEW_WIDTH, PREVIEW_HEIGHT))
                point_shader.uniform_int("holes_count", len(points))
                for i, c in enumerate(points):
                    point_shader.uniform_float("holes[{}]".format(i), c)
                original_point_batch.draw(point_shader)

            gpu.matrix.load_projection_matrix(projection_matrix)
            line_shader.bind()
            line_shader.uniform_float("color", get_active_color())
            line_shader.uniform_int("points_count", len(points))
            for i, c in enumerate(points):
                line_shader.uniform_float("points[{}]".format(i), c)
            line_batch.draw(line_shader)

            point_shader.bind()
            point_shader.uniform_int("holes_count", 0)
            point_batch.draw(point_shader)

            bgl.glLineWidth(1.0)
            bgl.glDisable(bgl.GL_LINE_SMOOTH)

        buffer = bgl.Buffer(bgl.GL_FLOAT, PREVIEW_WIDTH * PREVIEW_HEIGHT * 4)
        bgl.glReadBuffer(bgl.GL_BACK)
        bgl.glReadPixels(0, 0, PREVIEW_WIDTH, PREVIEW_HEIGHT, bgl.GL_RGBA, bgl.GL_FLOAT, buffer)

    offscreen.free()
    return buffer


def render_preview(collection_name, preview_name, shape, rotation=None):
    preview = get_preview(collection_name, preview_name)
    preview.image_pixels_float = render(shape, rotation)


def create_shaders():
    global point_shader
    global line_shader

    point_shader = gpu.types.GPUShader(point_vertex_shader, point_fragment_shader)
    line_shader = gpu.types.GPUShader(line_vertex_shader, line_fragment_shader)


def remove_shaders():
    global point_shader
    global line_shader

    point_shader = None
    line_shader = None


def register():
    preview_collections["shape_types"] = previews.new()
    preview_collections["patterns"] = previews.new()
    create_shaders()


def unregister():
    for pcoll in preview_collections.values():
        previews.remove(pcoll)
    remove_shaders()

atexit.register(remove_shaders)