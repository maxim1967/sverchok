import bpy
from node_s import *
from util import *

class GenVectorsNode(Node, SverchCustomTreeNode):
    ''' Generator vectors '''
    bl_idname = 'GenVectorsNode'
    bl_label = 'Vectors in'
    bl_icon = 'OUTLINER_OB_EMPTY'
    
    def init(self, context):
        self.inputs.new('StringsSocket', "X", "X")
        self.inputs.new('StringsSocket', "Y", "Y")
        self.inputs.new('StringsSocket', "Z", "Z")
        self.outputs.new('VerticesSocket', "Vectors", "Vectors")
        
    def update(self):
        # inputs
        if self.inputs['X'].links and \
            type(self.inputs['X'].links[0].from_socket) == StringsSocket:
            if not self.inputs['X'].node.socket_value_update:
                self.inputs['X'].node.update()
            X_ = SvGetSocketAnyType(self,self.inputs['X'])
        else:
            X_ = [[0.0]]
        
        if self.inputs['Y'].links and \
            type(self.inputs['Y'].links[0].from_socket) == StringsSocket:
            if not self.inputs['Y'].node.socket_value_update:
                self.inputs['Y'].node.update()
            Y_ = SvGetSocketAnyType(self,self.inputs['Y'])
        else:
            Y_ = [[0.0]]
            
        if self.inputs['Z'].links and \
            type(self.inputs['Z'].links[0].from_socket) == StringsSocket:
            if not self.inputs['Z'].node.socket_value_update:
                self.inputs['Z'].node.update()
            Z_ = SvGetSocketAnyType(self,self.inputs['Z'])
        else:
            Z_ = [[0.0]]
        
        # outputs
        if 'Vectors' in self.outputs and len(self.outputs['Vectors'].links)>0:
           
            max_obj = max(len(X_), len(Y_), len(Z_))
            self.fullList(X_,max_obj)
            self.fullList(Y_,max_obj)
            self.fullList(Z_,max_obj)
            
            series_vec = []
            for i in range(max_obj):
                X = X_[i]
                Y = Y_[i]
                Z = Z_[i]
            
                max_num = max(len(X), len(Y), len(Z))
                
                fullList(X,max_num)
                fullList(Y,max_num)
                fullList(Z,max_num)
            
                series_vec.append(list(zip(X,Y,Z)))
 
            SvSetSocketAnyType(self, 'Vectors',series_vec)
            #print (series_vec)
            
    def fullList(self, l, count):
        d = count - len(l)
        if d > 0:
            l.extend([l[-1] for a in range(d)])
        return
                
    def update_socket(self, context):
        self.update()

def register():
    bpy.utils.register_class(GenVectorsNode)
    
def unregister():
    bpy.utils.unregister_class(GenVectorsNode)

if __name__ == "__main__":
    register()