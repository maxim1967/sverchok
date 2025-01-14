# This file is part of project Sverchok. It's copyrighted by the contributors
# recorded in the version control history of the file, available from
# its original location https://github.com/nortikin/sverchok/commit/master
#
# SPDX-License-Identifier: GPL3
# License-Filename: LICENSE

import bpy
from bpy.props import FloatProperty, EnumProperty, BoolProperty, StringProperty
from mathutils import Vector

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.utils.nodes_mixins.sv_animatable_nodes import SvAnimatableNode
from sverchok.utils.nodes_mixins.show_3d_properties import Show3DProperties
from sverchok.utils.sv_operator_utils import SvGenericNodeLocator
from sverchok.data_structure import updateNode, zip_long_repeat, split_by_count
from sverchok.utils.curve.algorithms import concatenate_curves
from sverchok.utils.curve.bezier import SvCubicBezierCurve

import json

class SvBezierInLiteCallbackOp(bpy.types.Operator, SvGenericNodeLocator):

    bl_idname = "node.sv_bezier_in_lite_callback"
    bl_label = "Bezier In Lite Callback"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    

    def execute(self, context):
        """
        returns the operator's 'self' too to allow the code being called to
        print from self.report.
        """
        node = self.get_node(context)
        if node:
            node.get_objects_from_scene(self)
            return {'FINISHED'}

        return {'CANCELLED'}
        
class SvBezierInLiteNode(Show3DProperties, bpy.types.Node, SverchCustomTreeNode, SvAnimatableNode):
    """
    Triggers: Input Bezier
    Tooltip: Get Bezier Curve objects from scene
    """
    bl_idname = 'SvBezierInLiteNode'
    bl_label = 'Bezier In Lite'
    bl_icon = 'OUTLINER_OB_EMPTY'
    sv_icon = 'SV_OBJECTS_IN'
    
    do_not_add_obj_to_scene: BoolProperty(
        default=False,
        description="Do not add the object to the scene if this node is imported from elsewhere")
        
    apply_matrix: BoolProperty(
        name = "Apply matrices",
        description = "Apply object matrices to control points",
        default = True,
        update = updateNode)

    currently_storing: BoolProperty()
    obj_name: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    node_dict = {}
    
    def drop(self):
        self.obj_name = ""
        self.currently_storing = False
        self.node_dict[hash(self)] = {}    
        
    def get_objects_from_scene(self, ops):
        """
        Collect selected objects
        """

        names = [obj.name for obj in bpy.data.objects if (obj.select_get() and len(obj.users_scene) > 0 and len(obj.users_collection) > 0)]
        
        for name in names:
           self.obj_name.add().name = name

        if not self.obj_name:
            ops.report({'WARNING'}, "Warning, no selected objects in the scene")
            return
            
        self.process_node(None)
            
        if names:
            with self.sv_throttle_tree_update():

                self.node_dict[hash(self)] = {
                    'Curves': list([v.co[:] for v in names.curve]),
                    'ControlPoints': [list(p.curve) for p in names.controls],
                    'Matrices': self.apply_matrix
                }
                self.obj_name.clear()
                self.currently_storing = True

        else:
            self.error("No object selected")
    
        
    def get_curve(self, spline, matrix):
        segments = []
        pairs = zip(spline.bezier_points, spline.bezier_points[1:])
        if spline.use_cyclic_u:
            pairs = list(pairs) + [(spline.bezier_points[-1], spline.bezier_points[0])]
        points = []
        is_first = True
        for p1, p2 in pairs:
            c0 = p1.co
            c1 = p1.handle_right
            c2 = p2.handle_left
            c3 = p2.co
            if self.apply_matrix:
                c0, c1, c2, c3 = [tuple(matrix @ c) for c in [c0, c1, c2, c3]]
            else:
                c0, c1, c2, c3 = [tuple(c) for c in [c0, c1, c2, c3]]
            points.append([c0, c1, c2, c3])
            segment = SvCubicBezierCurve(c0, c1, c2, c3)
            segments.append(segment)
        return points, concatenate_curves(segments)
        
    def sv_init(self, context):
        self.outputs.new('SvCurveSocket', 'Curves')
        self.outputs.new('SvVerticesSocket', 'ControlPoints')
        self.outputs.new('SvMatrixSocket', 'Matrices')
        
    def draw_obj_names(self, layout):
        # display names currently being tracked, stop at the first 5..
        if self.obj_name:
            remain = len(self.obj_name) - 5

            for i, obj_ref in enumerate(self.obj_name):
                layout.label(text=obj_ref.name)
                if i > 4 and remain > 0:
                    postfix = ('' if remain == 1 else 's')
                    more_items = '... {0} more item' + postfix
                    layout.label(text=more_items.format(remain))
                    break
        else:
            layout.label(text='--None--')
        
    def draw_buttons(self, context, layout):
        callback = 'node.sv_bezier_in_lite_callback'

        col = layout.column(align=True)
        row = col.row(align=True)

        row = col.row()
        op_text = "Get selection"  # fallback

        try:
            addon = context.preferences.addons.get(sverchok.__name__)
            if addon.preferences.over_sized_buttons:
                row.scale_y = 4.0
                op_text = "G E T"
        except:
            pass

        self.wrapper_tracked_ui_draw_op(row, callback, text=op_text)
        
        layout.prop(self, 'apply_matrix', toggle=True)

        self.draw_obj_names(layout)
        
    def pass_data_to_sockets(self):
        curv_data = self.node_dict.get(hash(self))
        if curv_data:
            for socket in self.outputs:
                if socket.is_linked:
                    socket.sv_set([curv_data[socket.name]])
                    
    def process(self):
    
        if not hash(self) in self.node_dict:
            if not self.obj_name:
                return

            curves_out = []
            matrices_out = []
            controls_out = []
            for item in self.obj_name:
                object_name = item.name
                obj = bpy.data.objects.get(object_name)
                if not obj:
                    continue
                with self.sv_throttle_tree_update():
                    matrix = obj.matrix_world
                    if obj.type != 'CURVE':
                        self.warning("%s: not supported object type: %s", object_name, obj.type)
                        continue
                    for spline in obj.data.splines:
                        if spline.type != 'BEZIER':
                            self.warning("%s: not supported spline type: %s", spline, spline.type)
                            continue
                        controls, curve = self.get_curve(spline, matrix)
                        curves_out.append(curve)
                        controls_out.append(controls)
                        matrices_out.append(matrix)

            self.outputs['Curves'].sv_set(curves_out)
            self.outputs['ControlPoints'].sv_set(controls_out)
            self.outputs['Matrices'].sv_set(matrices_out)

        self.pass_data_to_sockets()
        
    def load_from_json(self, node_data: dict, import_version: float):
        if 'curv' not in node_data:
            return  # looks like a node was empty when it was imported
        curv = node_data['curv']
        name = node_data['params']["obj_name"]
        curv_dict = json.loads(curv)

        if not curv_dict:
            print(self.name, 'contains no flatten curv')
            return

        unrolled_curv = unflatten(curv_dict)
        verts = unrolled_curv['Curves']
        controlpoints = unrolled_curv['ControlPoints']
        matrix = unrolled_curv['Matrices']

        if self.do_not_add_obj_to_scene:
            self.node_dict[hash(self)] = unrolled_curv
            self.obj_name = name
            return
            
    def save_to_json(self, node_data: dict):
        # generate flat data, and inject into incoming storage variable
        obj = self.node_dict.get(hash(self))
        print(obj)
        if not obj:
            self.error('failed to obtain local geometry, can not add to json')
            return

        node_data['curv'] = json.dumps(flatten(obj))


def register():
    bpy.utils.register_class(SvBezierInLiteCallbackOp)
    bpy.utils.register_class(SvBezierInLiteNode)

def unregister():
    bpy.utils.unregister_class(SvBezierInLiteNode)
    bpy.utils.unregister_class(SvBezierInLiteCallbackOp)
