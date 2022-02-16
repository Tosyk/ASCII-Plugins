bl_info = {
    "name": "secASCII",
    "description": "Import ASCII files.",
    "author": "SecaProject",
    "version": (0, 8, 5, 1),
    "blender": (2, 80, 0),
    "location": "File > Import",
    "warning": "",
    "wiki_url": "https://secaproject.com/"
                "blender_addon_ascii",
    "tracker_url": "https://secaproject.com/blender_addon_ascii#report",
    "support": "OFFICIAL",
    "category": "Import",
}

import os
import bpy
import sys
import math
import time
import bmesh
import struct
import mathutils
from bpy.props import BoolProperty, StringProperty, EnumProperty, FloatProperty, CollectionProperty
from bpy.types import Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper

def readData(f, line, uvCount, bones, self):
    vertex       = f[line + 0][:-1].split(" ")
    x            = float(vertex[0])
    y            = float(vertex[1])
    z            = float(vertex[2])
    vertexs      = (x,y,z)

    if self.loadNormal:
        normal   = f[line + 1][:-1].split(" ")
        x        = float(normal[0])
        y        = float(normal[1])
        z        = float(normal[2])
        normals  = mathutils.Vector((x,y,z)).normalized()
        #normals  = mathutils.Vector((0,1,0)).normalized()
    else:
        normals  = False

    if self.loadVertexColor:
        color    = f[line + 2][:-1].split(" ")
        r        = int(color[0])/255
        g        = int(color[1])/255
        b        = int(color[2])/255
        a        = int(color[3])/255
        colors   = (r, g, b, a)
    else:
        colors   = False

    uvs          = []
    if self.loadUV:
        for j in range(uvCount):
            uv   = f[line + 3 + j][:-1].split(" ")
            u    = float(uv[0])
            v    = 1-float(uv[1])
            uvs.append((u,v))

    weights      = []
    if bones > 0:
        weightId = f[line + 3 + uvCount][:-1].split(" ")
        weight   = f[line + 4 + uvCount][:-1].split(" ")
        for j in range( len(weightId) ):
            weights.append( [ int(weightId[j]), float(weight[j]) ] )
    else:
        weights  = False
    return [vertexs, normals, colors, uvs, weights ]

def createMaterial(materialName, self, textureList):
    mat = bpy.data.materials.get(materialName)
    if mat is None:
        mat                                         = bpy.data.materials.new(name=materialName)
        mat.use_nodes                               = True
        bsdf                                        = mat.node_tree.nodes["Principled BSDF"]
        bsdf.hide                                   = True
        bsdf.width                                  = 0.0
        bsdf.location                               = (0, 0)
        bsdf.inputs[5].default_value                = 0
        bsdf.inputs["Roughness"].default_value      = 1
        matOut                                      = mat.node_tree.nodes["Material Output"]
        matOut.hide                                 = True
        matOut.width                                = 0.0
        matOut.location                             = (250, 0)

        mat.node_tree.links.new(matOut.inputs['Surface'],       bsdf.outputs['BSDF'])

        if textureList[0][0] and textureList[0][0] != "no_diffuse":
            texDiffuse                              = mat.node_tree.nodes.new('ShaderNodeTexImage')
            texDiffuse.hide                         = True
            texDiffuse.width                        = 0.0
            texDiffuse.location                     = (-49, 157)
            texDiffuse.interpolation                = 'Closest'
            if bpy.data.images.get(textureList[0][0]+self.textureFormat) is None:
                if os.path.isfile(self.texturePath+"/"+textureList[0][0]+self.textureFormat):
                    pathTo          = self.texturePath+"/"+textureList[0][0]+self.textureFormat
                    texDiffuse.image = bpy.data.images.load(pathTo)
                    mat.blend_method = 'HASHED'
                    mat.node_tree.links.new(bsdf.inputs['Base Color'], texDiffuse.outputs['Color'])
                    mat.node_tree.links.new(bsdf.inputs['Alpha'],      texDiffuse.outputs['Alpha'])
                    #mat.node_tree.links.new(bsdf.inputs['Base Color'], texNormal.outputs['Color'])
                else:
                    print("Could't find",self.texturePath+"/"+textureList[0][0]+self.textureFormat)
            else:
                texDiffuse.image = bpy.data.images.get(textureList[0][0]+self.textureFormat)

        if len( textureList ) > 1:
            if textureList[1][0] and textureList[1][0] != "no_normal":
                texNormal                                   = mat.node_tree.nodes.new('ShaderNodeTexImage')
                texNormal.hide                              = True
                texNormal.width                             = 0.0
                texNormal.location                          = (-100, 20)
                texNormal.interpolation                     = 'Closest'
                if bpy.data.images.get(textureList[1][0]+self.textureFormat) is None:
                    if os.path.isfile(self.texturePath+"/"+textureList[1][0]+self.textureFormat):
                        pathTo          = self.texturePath+"/"+textureList[1][0]+self.textureFormat
                        texNormal.image = bpy.data.images.load(pathTo)
                        mat.node_tree.links.new(bsdf.inputs['Normal'],      texNormal.outputs['Color'])
                        #mat.node_tree.links.new(bsdf.inputs['Base Color'], texNormal.outputs['Color'])
                    else:
                        print("Could't find",self.texturePath+"/"+textureList[1][0]+self.textureFormat)
                else:
                    texNormal.image = bpy.data.images.get(textureList[1][0]+self.textureFormat)

    return mat

def readASCII280(context, f, collect, fileName, self):
    # SKELETON
    boneCount = int(f[0])
    if boneCount != 0 and self.loadSkeleton:
        skl    = bpy.data.objects.new("arm_"+fileName, bpy.data.armatures.new("armature"))
        skl.data.display_type = "STICK"
        collect.objects.link(skl)
        bpy.context.view_layer.objects.active = skl

        if self.upAxis == "1":
            skl.rotation_euler = (math.radians(90), 0, math.radians(90) ) 
        skl.scale = ( 1/self.scale, 1/self.scale, 1/self.scale )

        boneList = []
        bpy.ops.object.mode_set(mode='EDIT')
        for h in range(boneCount):
            name        = f[h * 3 + 1][:-1]
            parent      = int(f[h * 3 + 2])
            coords      = f[h * 3 + 3][:-1].split(" ")
            quat        = mathutils.Quaternion([float(coords[6]), float(coords[3]), float(coords[4]), float(coords[5])]).to_matrix().to_4x4()
            locate      = [float(coords[0]), float(coords[1]), float(coords[2])]

            pos         = mathutils.Matrix.Translation(locate)
            bone        = skl.data.edit_bones.new(name)
            bone.head   = mathutils.Vector(locate)
            bone.tail   = mathutils.Vector((locate[0], locate[1]+0.001, locate[2] ))
            bone.matrix = pos @ quat
            boneList.append(name)
            if parent != -1:
               bone.parent = skl.data.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')

    # MESH
    currentLine = boneCount * 3 + 1
    meshCount   = int(f[currentLine])
    currentLine += 1
    textureTotal = 0
    for h in range(meshCount):
        # SUBMESH INFO
        meshName     = f[currentLine+0][:-1]
        mesh         = bpy.data.meshes.new(fileName+"_" + str(h).zfill(2))
        uvCount      = int(f[currentLine+1])
        textureCount = int(f[currentLine+2])
        if self.createMat:
            textureList  = []
            for i in range(textureCount):
                textureName = f[currentLine + 3 + i*2 + 0 ][:-1].split(".")[0]
                unkn        = f[currentLine + 3 + i*2 + 1 ][:-1]
                textureList.append( [textureName, unkn] )
            mat     = createMaterial( fileName + "_mat_" + str(h), self, textureList )
            mesh.materials.append(mat)

        vertexCount  = int(f[currentLine + 3 + textureCount * 2])
        vertexLine   = currentLine + 4 + textureCount * 2
        linesPerVertex = 3 + uvCount
        if boneCount != 0:
            linesPerVertex += 2
        triangCount  = int(f[vertexLine+vertexCount * linesPerVertex])

        faces        = []
        vertexs      = []
        normals      = []
        vColors      = []
        uvs          = []
        weights      = []
        for i in range(vertexCount):
            values   = readData(f, vertexLine + i * linesPerVertex, uvCount, boneCount, self)
            vertexs.append( values[0] )
            normals.append( values[1] )
            vColors.append( values[2] )
            uvs.append(     values[3] )
            weights.append( values[4] )

        # TRIANGLES INFO
        for i in range(triangCount):
            triangle = f[vertexLine + vertexCount * linesPerVertex + i + 1][:-1].split(" ")
            faces.append( [ int(triangle[2]), int(triangle[1]), int(triangle[0]) ] )


        mesh.from_pydata(vertexs, [], faces)
        object       = bpy.data.objects.new(meshName, mesh)
        bm           = bmesh.new()
        bm.from_mesh(mesh)

        # Swap axis if activated
        if self.upAxis == "1":
            object.rotation_euler = (math.radians(90), 0, math.radians(90) ) 

        object.scale = ( 1/self.scale, 1/self.scale, 1/self.scale )

        # UV's
        if self.loadUV:
            uvLayer = []
            for i in range(uvCount):
                uvLayer.append( bm.loops.layers.uv.new() )
            for i in bm.faces:
                for j in range(uvCount):
                    i.loops[0][uvLayer[j]].uv=uvs[faces[i.index][0]][j]
                    i.loops[1][uvLayer[j]].uv=uvs[faces[i.index][1]][j]
                    i.loops[2][uvLayer[j]].uv=uvs[faces[i.index][2]][j]
                i.material_index = h

        # Vertex colors
        if self.loadVertexColor:
            color_layer  = bm.loops.layers.color.new()
            for i in bm.faces:
                i.loops[0][color_layer] = (vColors[faces[i.index][0]])
                i.loops[1][color_layer] = (vColors[faces[i.index][1]])
                i.loops[2][color_layer] = (vColors[faces[i.index][2]])

        # Weights
        if boneCount != 0 and self.loadSkeleton:
            mod = object.modifiers.new(type="ARMATURE", name="arm_"+fileName)
            mod.object = skl
            mod.use_vertex_groups = True

            weight_layer = bm.verts.layers.deform.new()
            for i in boneList:
                object.vertex_groups.new(name=i)

            for i in bm.verts:
                for j in weights[i.index]:
                    i[weight_layer][j[0]] = j[1]

        bm.to_mesh(mesh)
        bm.free()

        # Normals
        if self.loadNormal:
            for poly in mesh.polygons:
                poly.use_smooth = True

            mesh.normals_split_custom_set_from_vertices(normals)
            mesh.use_auto_smooth = True

        collect.objects.link(object)
        textureTotal += textureCount
        currentLine  += 5 + textureCount * 2 + vertexCount * linesPerVertex + triangCount

    # ANIMATION
    if len(f) >= currentLine + 2:
        animCount   = int(f[currentLine])
        currentLine += 1
        for h in range(animCount):
            animName     = f[currentLine+0][:-1]
            totalFrames  = int(f[currentLine+1])
            currentLine  += 2
            for i in range(totalFrames):
                frame    = int(f[currentLine].split(" ")[0])
                nBones   = int(f[currentLine].split(" ")[1])

    if boneCount != 0 and self.loadSkeleton:
        bpy.ops.object.mode_set(mode='POSE')
    return

class asciitool(Operator, ImportHelper):
    bl_idname = "ascii.project"
    bl_label = "Load ascii file"

    filter_glob: StringProperty(
        description = "ASCII file loader",
        default	 = "*.ascii",
        options	 = {'HIDDEN'},
        maxlen	  = 255,
    )

    upAxis: EnumProperty(
        name="Up axis",
        description="Switch the 'up' Axis of the imported models",
        items=(
            ("0", "Original", "Original from the file"),
            ("1", "Change", "Change to (Y, Z, X)"),
        ),
        default="1",
    )

    scale: FloatProperty(
        name="Scale",
        description="Reduce the scale of the model. Recommended if you need a specific scale",
        default=1.0,
        soft_min=0.0,
        step=10,
        min=1,
    )

    loadSkeleton: BoolProperty(
        name="Load skeleton",
        description="Load or ignore the Skeletan\nDisable isn't recommended",
        default=True,
    )

    loadNormal: BoolProperty(
        name="Load normals",
        description="Use orginal file normals or generate new ones\nDisable isn't recommended but faster",
        default=True,
    )

    loadVertexColor: BoolProperty(
        name="Load Vertex Colors",
        description="Load Vertex Colors, useful for blending textures or adjusting colors\nDisable isn't recommended",
        default=False,
    )

    loadUV: BoolProperty(
        name="Load UV",
        description="Load all object UV channels or ignore them\nDisable isn't recommended but faster",
        default=False,
    )

    createMat: BoolProperty(
        name="Materials",
        description="Create materials",
        default=False,
    )

    joinObj: BoolProperty(
        name="Join all objects",
        description="It will join the objects from each imported file",
        default=False,
    )

    reset: BoolProperty(
        name="Reset",
        description="Will remove objects, meshes, lights, materials, images and collections from the scene",
        default=False,
    )

    textureFormat: EnumProperty(
        name="Texture format",
        description="Choose the format to load",
        items=(
            (".tga", "TGA", ""),
            (".png", "PNG", ""),
            (".dds", "DDS", "Blender doesn't support all DDS types"),
            (".jpg", "JPG", ""),
        ),
        default=".dds",
    )

    texturePath: StringProperty(
        name="Texture Path",
        description="Useful when texture path isn't in the same place as model file",
        default="./",
    )

    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
    )

    directory: StringProperty(
        subtype='DIR_PATH',
    )

    def execute(self, context):
        if self.reset:
            bpy.ops.wm.read_factory_settings(use_empty=False)
        startScript  = time.time()
        self.texturePath  = self.texturePath if self.texturePath[1] == ":" else os.path.abspath(self.directory+self.texturePath)
        print("Configuration")
        print("  Up axis:        Original" if self.upAxis == "0"   else "  Up axis:        Change")
        print("  Scale:          Original" if self.scale == 1      else "  Scale:          "+str(self.scale)+":1")
        print("  Skeleton:       Original" if self.loadSkeleton    else "  Skeleton:       Skip")
        print("  Normals:        Original" if self.loadNormal      else "  Normals:        Skip")
        print("  Vertex Colors:  Original" if self.loadVertexColor else "  Vertex Colors:  Skip")
        print("  UV coords:      Original" if self.loadUV          else "  UV coords:      Skip")
        print("  Join objects:   Yes"      if self.joinObj         else "  Join objects:   No")
        print("  Texture format:",self.textureFormat)
        print("  Texture path:  ",self.texturePath)
        print("================")

        for file_elem in self.files:
            file      = self.directory+file_elem.name
            fileName  = bpy.path.basename(file)
            fileExtn  = fileName.split(".")[-1]
            fileName  = fileName.split(".")[0]
            binfile   = open(file, 'r').readlines()

            print(" ",fileName)
            start_time = time.time()
            if fileExtn == "ascii":
                if bpy.data.collections.get(fileName+"_col") is not None:
                    collect = bpy.data.collections.get(fileName+"_col")
                else:
                    collect  = bpy.data.collections.new(fileName+"_col")
                    bpy.context.scene.collection.children.link( collect )

                readASCII280(context, binfile, collect, fileName, self)

                if self.joinObj:
                    isTheFirstOne = True
                    for obj in bpy.data.collections[fileName+"_col"].all_objects:
                        if obj.type == "ARMATURE":
                            armature = obj
                        if obj.type == "MESH":
                            if isTheFirstOne:
                                bpy.context.view_layer.objects.active = obj
                                isTheFirstOne = False
                            obj.select_set(True)
                    bpy.ops.object.join()
                    bpy.context.active_object.select_set(False)
                    bpy.context.view_layer.objects.active = armature
            elapsedTime = time.time() - start_time
            print("   ",elapsedTime, "secs")
        totalScript = time.time() - startScript
        print("  Total:",totalScript, "secs")
        return {"FINISHED"}

def menu_func_import(self, context):
    self.layout.operator(asciitool.bl_idname, text="ASCII (*.ascii)")

def register():
    bpy.utils.register_class(asciitool)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(asciitool)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
    os.system('cls')
    bpy.ops.ascii.project('INVOKE_DEFAULT')
