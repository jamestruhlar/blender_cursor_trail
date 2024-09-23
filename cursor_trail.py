import bpy
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, FloatProperty
from bpy.types import AddonPreferences, Panel, Operator, Menu
import gpu
from gpu_extras.batch import batch_for_shader
import random
import time
bl_info = {
    "name": "Cursor Trail",
    "blender": (4, 2, 0),
    "category": "3D View",
    "description": "Adds a cursor trail effect in the 3D View.",
    "author": "mdcrtv",
    "version": (0, 0),
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
        max=400
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
class VIEW3D_MT_cursor_trail_context_menu(Menu):
    bl_label = "Options"
    def draw(self, context):
        layout = self.layout
        layout.operator("view3d.cursor_trail_reset", text="Reset to Default Values")
        layout.operator("view3d.cursor_trail_save_default", text="Save as Default")
class VIEW3D_OT_cursor_trail_reset(Operator):
    bl_idname = "view3d.cursor_trail_reset"
    bl_label = "Reset to default"
    bl_description = "Reset all cursor trail settings to their default values"
    def execute(self, context):
        preferences = context.preferences.addons[__name__].preferences
        preferences.reset_preferences()
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
            layout.prop(preferences, "trail_start_color", text="Start Color")
            layout.prop(preferences, "trail_end_color", text="End Color")
    def draw_header_preset(self, _context):
        layout = self.layout
        layout.menu("VIEW3D_MT_cursor_trail_context_menu", icon='DOWNARROW_HLT', text="")
trail_points = []
draw_handler = None
last_mouse_move_time = 0
last_mouse_pos = (0, 0)
last_jitter = 0.0
def draw_cursor_trail():
    if len(trail_points) < 2:
        return
    preferences = bpy.context.preferences.addons[__name__].preferences
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    start_color = preferences.trail_start_color
    end_color = preferences.trail_end_color
    for i in range(len(trail_points) - 1):
        start = trail_points[i][0]
        end = trail_points[i + 1][0]
        t = 1 - i / (len(trail_points) - 1)
        interpolated_color = (
            start_color[0] * t + end_color[0] * (1 - t),
            start_color[1] * t + end_color[1] * (1 - t),
            start_color[2] * t + end_color[2] * (1 - t),
            start_color[3] * t + end_color[3] * (1 - t)
        )
        shader.bind()
        shader.uniform_float("color", interpolated_color)
        gpu.state.line_width_set(preferences.trail_width)
        batch = batch_for_shader(shader, 'LINES', {"pos": [start, end]})
        batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')
def update_trail(region, mouse_pos):
    global trail_points, last_mouse_move_time, last_mouse_pos, last_jitter
    preferences = bpy.context.preferences.addons[__name__].preferences
    region_x = mouse_pos[0] - region.x
    region_y = mouse_pos[1] - region.y
    current_time = time.time()
    dx = mouse_pos[0] - last_mouse_pos[0]
    dy = mouse_pos[1] - last_mouse_pos[1]
    distance = (dx**2 + dy**2)**0.5
    movement_speed = distance / max(current_time - last_mouse_move_time, 1e-6) if last_mouse_move_time != 0 else 0.0
    if movement_speed > 0:
        last_jitter = preferences.trail_jitter
        jittered_x = region_x + random.uniform(-last_jitter, last_jitter)
        jittered_y = region_y + random.uniform(-last_jitter, last_jitter)
        trail_points.append(((jittered_x, jittered_y), current_time, movement_speed))
    else:
        last_jitter = max(0, last_jitter - 0.01)
    last_mouse_move_time = current_time
    last_mouse_pos = mouse_pos
    trail_points = [p for p in trail_points if current_time - p[1] < 1]
    max_points = preferences.trail_length
    if len(trail_points) > max_points:
        trail_points = trail_points[-max_points:]
class CursorTrailPreferences(AddonPreferences):
    def reset_preferences(self):
        self.cursor_trail = False
        self.trail_length = 50
        self.trail_width = 2.0
        self.trail_jitter = 0.0
        self.trail_start_color = (0.0, 0.1, 1.0, 0.0)
        self.trail_end_color = (1.0, 0.3, 0.0, 0.75)
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
        max=400
    )
    trail_width: FloatProperty(
        name="Width",
        description="Width of the trail",
        default=5.0,
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
class VIEW3D_OT_cursor_trail(Operator):
    bl_idname = "view3d.cursor_trail"
    bl_label = "Cursor Trail"
    _timer = None
    def modal(self, context, event):
        preferences = context.preferences.addons[__name__].preferences
        if preferences.cursor_trail:
            if event.type == 'TIMER':
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                update_trail(region, (event.mouse_x, event.mouse_y))
                                area.tag_redraw()
                                break
                        break
            if event.type == 'MOUSEMOVE':
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
            self._timer = context.window_manager.event_timer_add(0.03, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            return {'FINISHED'}
class VIEW3D_PT_cursor_trail(Panel):
    bl_label = "Cursor Trail"
    bl_idname = "VIEW3D_PT_cursor_trail"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'
    def draw(self, context):
        layout = self.layout
        preferences = context.preferences.addons[__name__].preferences
        layout.prop(preferences, "cursor_trail", text="Enable")
        if preferences.cursor_trail:
            layout.prop(preferences, "trail_length", text="Length")
            layout.prop(preferences, "trail_width", text="Width")
            layout.prop(preferences, "trail_jitter", text="Jitter")
            # The labels are intentionally flipped since the trail render 'ends' at the cursor
            layout.prop(preferences, "trail_end_color", text="Start Color")
            layout.prop(preferences, "trail_start_color", text="End Color")
    def draw_header(self, context):
        layout = self.layout
        layout.operator("wm.call_menu", text="", icon='DOWNARROW_HLT').name = "VIEW3D_MT_cursor_trail_context_menu"
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
    bpy.app.handlers.load_post.append(load_handler)
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
    bpy.app.handlers.load_post.remove(load_handler)
if __name__ == "__main__":
    register()

    