import bpy
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, FloatProperty
from bpy.types import AddonPreferences, Panel, Operator, Menu
import gpu
from gpu_extras.batch import batch_for_shader
import random
import time
from mathutils import Vector

bl_info = {
    "name": "Cursor Trail",
    "blender": (4, 2, 0),
    "category": "3D View",
    "description": "Adds a cursor trail effect in the 3D View.",
    "author": "mdcrtv",
    "version": (0, 1),
    "tracker_url": "https://github.com/jamestruhlar/blender_cursor_trail.git",
    "support": "COMMUNITY",
}

class CursorTrailPreferences(AddonPreferences):
    bl_idname = __name__

    cursor_trail: BoolProperty(
        name="Cursor Trail",
        description="Enable or disable cursor trail",
        default=False,
        update=lambda self, context: update_cursor_trail(self, context)
    )
    trail_length: IntProperty(
        name="Length",
        description="Length of the trail",
        default=50,
        min=10,
        max=500
    )
    trail_width: FloatProperty(
        name="Width",
        description="Width of the trail",
        default=2.0,
        min=1,
        max=10.0
    )
    trail_jitter: FloatProperty(
        name="Jitter",
        description="Amount of random jitter to apply to the trail points",
        default=0.0,
        min=0.0,
        max=20.0
    )
    trail_start_color: FloatVectorProperty(
        name="Start Color",
        description="Start color of the cursor trail",
        default=(0.0, 0.1, 1.0, 0.0),
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0
    )
    trail_end_color: FloatVectorProperty(
        name="End Color",
        description="End color of the cursor trail",
        default=(1.0, 0.3, 0.0, 0.75),
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "cursor_trail")
        layout.prop(self, "trail_length")
        layout.prop(self, "trail_width")
        layout.prop(self, "trail_jitter")
        layout.prop(self, "trail_start_color")
        layout.prop(self, "trail_end_color")

    def reset_preferences(self):
        self.trail_length = 50
        self.trail_width = 2.0
        self.trail_jitter = 0.0
        self.trail_start_color = (0.0, 0.1, 1.0, 0.0)
        self.trail_end_color = (1.0, 0.3, 0.0, 0.75)

    def save_favorite(self):
        return {
            "trail_length": self.trail_length,
            "trail_width": self.trail_width,
            "trail_jitter": self.trail_jitter,
            "trail_start_color": self.trail_start_color[:],
            "trail_end_color": self.trail_end_color[:]
        }

    def load_favorite(self, favorite):
        self.trail_length = favorite["trail_length"]
        self.trail_width = favorite["trail_width"]
        self.trail_jitter = favorite["trail_jitter"]
        self.trail_start_color = favorite["trail_start_color"]
        self.trail_end_color = favorite["trail_end_color"]

class VIEW3D_MT_cursor_trail_context_menu(Menu):
    bl_label = "Options"
    def draw(self, context):
        layout = self.layout
        layout.operator("view3d.cursor_trail_reset", text="Reset to Default")
        layout.operator("view3d.cursor_trail_set_favorite", text="Set Favorite")
        layout.operator("view3d.cursor_trail_load_favorite", text="Load Favorite")

class VIEW3D_OT_cursor_trail_reset(Operator):
    bl_idname = "view3d.cursor_trail_reset"
    bl_label = "Reset to default"
    bl_description = "Reset all cursor trail settings to their default values"
    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        current_state = preferences.cursor_trail
        preferences.reset_preferences()
        preferences.cursor_trail = current_state
        return {'FINISHED'}

class VIEW3D_OT_cursor_trail_set_favorite(Operator):
    bl_idname = "view3d.cursor_trail_set_favorite"
    bl_label = "Set as Favorite"
    bl_description = "Save current settings as favorite"
    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        favorite = preferences.save_favorite()
        context.window_manager.cursor_trail_favorite = str(favorite)
        self.report({'INFO'}, "Cursor Trail settings saved as favorite")
        return {'FINISHED'}

class VIEW3D_OT_cursor_trail_load_favorite(Operator):
    bl_idname = "view3d.cursor_trail_load_favorite"
    bl_label = "Load Favorite"
    bl_description = "Load favorite settings"
    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        favorite_str = context.window_manager.cursor_trail_favorite
        if favorite_str:
            favorite = eval(favorite_str)
            current_state = preferences.cursor_trail
            preferences.load_favorite(favorite)
            preferences.cursor_trail = current_state
            self.report({'INFO'}, "Favorite Cursor Trail settings loaded")
        else:
            self.report({'WARNING'}, "No favorite settings saved yet")
        return {'FINISHED'}
    
class VIEW3D_PT_cursor_trail(Panel):
    bl_label = "Cursor Trail"
    bl_idname = "VIEW3D_PT_cursor_trail"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        preferences = context.preferences.addons[__name__].preferences
        layout.prop(preferences, "cursor_trail", text="Enable")
        if preferences.cursor_trail:
            layout.prop(preferences, "trail_length", text="Length")
            layout.prop(preferences, "trail_width", text="Width")
            layout.prop(preferences, "trail_jitter", text="Jitter")
            layout.prop(preferences, "trail_end_color", text="Start Color")
            layout.prop(preferences, "trail_start_color", text="End Color")

    def draw_header(self, context):
        layout = self.layout
        layout.operator("wm.call_menu", text="", icon='DOWNARROW_HLT').name = "VIEW3D_MT_cursor_trail_context_menu"

trail_points = []
draw_handler = None
last_mouse_move_time = 0
last_mouse_pos = (0, 0)
last_offset = Vector((0, 0))
is_moving = False
fade_start_time = 0

def update_trail(region, mouse_pos):
    global trail_points, last_mouse_move_time, last_mouse_pos, last_offset, is_moving, fade_start_time
    preferences = bpy.context.preferences.addons[__name__].preferences
    
    region_x = mouse_pos[0] - region.x
    region_y = mouse_pos[1] - region.y
    current_time = time.time()

    dx = mouse_pos[0] - last_mouse_pos[0]
    dy = mouse_pos[1] - last_mouse_pos[1]
    distance = (dx**2 + dy**2)**0.5
    movement_speed = distance / max(current_time - last_mouse_move_time, 1e-6) if last_mouse_move_time != 0 else 0.0

    movement_threshold = 1.0
    is_moving = movement_speed > movement_threshold

    if is_moving:
        direction = Vector((dx, dy)).normalized() if distance != 0 else Vector((0, 0))
        target_offset = direction * -3.0
        lerp_factor = 0.2
        new_offset = last_offset.lerp(target_offset, lerp_factor)

        max_speed = 1000
        speed_factor = min(movement_speed / max_speed, 1.0)
        jitter_amount = preferences.trail_jitter * speed_factor
        
        jittered_x = region_x + new_offset.x + random.uniform(-jitter_amount, jitter_amount)
        jittered_y = region_y + new_offset.y + random.uniform(-jitter_amount, jitter_amount)
        
        trail_points.append(((jittered_x, jittered_y), current_time))
        
        last_offset = new_offset

    fade_start_time = current_time

    last_mouse_move_time = current_time
    last_mouse_pos = mouse_pos

    fade_duration = 0.5
    trail_points = [p for p in trail_points if current_time - p[1] < fade_duration]

    max_points = preferences.trail_length
    if len(trail_points) > max_points:
        trail_points = trail_points[-max_points:]

def draw_cursor_trail():
    if len(trail_points) < 2:
        return
    
    preferences = bpy.context.preferences.addons[__name__].preferences
    shader = gpu.shader.from_builtin('SMOOTH_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(preferences.trail_width)
    
    start_color = preferences.trail_start_color
    end_color = preferences.trail_end_color

    vertices = []
    colors = []
    
    current_time = time.time()
    
    for i, (point, timestamp) in enumerate(trail_points):
        t = i / (len(trail_points) - 1)
        age = current_time - timestamp
        fade_factor = max(0, 1 - age / 2.0)
        
        color = (
            start_color[0] * (1-t) + end_color[0] * t,
            start_color[1] * (1-t) + end_color[1] * t,
            start_color[2] * (1-t) + end_color[2] * t,
            (start_color[3] * (1-t) + end_color[3] * t) * fade_factor
        )
        
        corrected_color = [pow(c, 1/2.2) for c in color[:3]] + [color[3]]
        
        vertices.append(point)
        colors.append(corrected_color)
    
    batch = batch_for_shader(shader, 'LINE_STRIP', {
        "pos": vertices,
        "color": colors,
    })
    
    shader.bind()
    batch.draw(shader)
    
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')

class VIEW3D_OT_cursor_trail(Operator):
    bl_idname = "view3d.cursor_trail"
    bl_label = "Cursor Trail"
    _timer = None

    def modal(self, context, event):
        preferences = context.preferences.addons[__name__].preferences
        if preferences.cursor_trail:
            if event.type in {'TIMER', 'MOUSEMOVE'}:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                update_trail(region, (event.mouse_x, event.mouse_y))
                                area.tag_redraw()
                                break
                        break
            return {'PASS_THROUGH'}
        else:
            context.window_manager.event_timer_remove(self._timer)
            return {'FINISHED'}

    def invoke(self, context, event):
        preferences = context.preferences.addons[__name__].preferences
        if preferences.cursor_trail:
            self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            return {'FINISHED'}

def update_cursor_trail(self, context):
    global draw_handler
    if self.cursor_trail:
        if draw_handler is None:
            draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_cursor_trail, (), 'WINDOW', 'POST_PIXEL')
        bpy.ops.view3d.cursor_trail('INVOKE_DEFAULT')
    else:
        if draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
            draw_handler = None
        global trail_points
        trail_points.clear()

@bpy.app.handlers.persistent
def load_handler(dummy):
    preferences = bpy.context.preferences.addons[__name__].preferences
    if preferences.cursor_trail:
        update_cursor_trail(preferences, bpy.context)

def register():
    bpy.utils.register_class(CursorTrailPreferences)
    bpy.utils.register_class(VIEW3D_OT_cursor_trail)
    bpy.utils.register_class(VIEW3D_PT_cursor_trail)
    bpy.utils.register_class(VIEW3D_MT_cursor_trail_context_menu)
    bpy.utils.register_class(VIEW3D_OT_cursor_trail_reset)
    bpy.utils.register_class(VIEW3D_OT_cursor_trail_set_favorite)
    bpy.utils.register_class(VIEW3D_OT_cursor_trail_load_favorite)
    bpy.app.handlers.load_post.append(load_handler)
    bpy.types.WindowManager.cursor_trail_favorite = bpy.props.StringProperty()

def unregister():
    global draw_handler
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None
    bpy.utils.unregister_class(CursorTrailPreferences)
    bpy.utils.unregister_class(VIEW3D_OT_cursor_trail)
    bpy.utils.unregister_class(VIEW3D_PT_cursor_trail)
    bpy.utils.unregister_class(VIEW3D_MT_cursor_trail_context_menu)
    bpy.utils.unregister_class(VIEW3D_OT_cursor_trail_reset)
    bpy.utils.unregister_class(VIEW3D_OT_cursor_trail_set_favorite)
    bpy.utils.unregister_class(VIEW3D_OT_cursor_trail_load_favorite)
    bpy.app.handlers.load_post.remove(load_handler)
    del bpy.types.WindowManager.cursor_trail_favorite

if __name__ == "__main__":
    register()
