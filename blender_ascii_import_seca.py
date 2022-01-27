bl_info = {
    "name": "secASCII",
    "description": "Import ASCII files.",
    "author": "SecaProject",
    "version": (0, 7, 1),
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

def readData(f, line, uvCount, bones, upAxis, scale, loadNormal, loadVrtxClr, loadUv):
    vertex   = f[line + 0][:-1].split(" ")
    if upAxis == "0":
        x    = float(vertex[0])/scale
        y    = float(vertex[1])/scale 
        z    = float(vertex[2])/scale
    else:
        y    = float(vertex[0])/scale
        z    = float(vertex[1])/scale
        x    = float(vertex[2])/scale
    vertexs  = (x,y,z)

    if loadNormal:
        normal   = f[line + 1][:-1].split(" ")
        if upAxis == "0":
            x        = float(normal[0])
            y        = float(normal[1])
            z        = float(normal[2])
        else:
            x        = float(normal[2])
            y        = float(normal[0])
            z        = float(normal[1])
        normals  = mathutils.Vector((x,y,z)).normalized()
        #normals  = mathutils.Vector((0,1,0)).normalized()
    else:
        normals  = False

    if loadVrtxClr:
        color    = f[line + 2][:-1].split(" ")
        r        = int(color[0])/255
        g        = int(color[1])/255
        b        = int(color[2])/255
        a        = int(color[3])/255
        colors   = (r, g, b, a)
    else:
        colors   = False

    uvs      = []
    if loadUv:
        for j in range(uvCount):
            uv   = f[line + 3 + j][:-1].split(" ")
            u    = float(uv[0])
            v    = 1-float(uv[1])
            uvs.append((u,v))

    weights  = []
    if bones > 0:
        weightId = f[line + 3 + uvCount][:-1].split(" ")
        weight   = f[line + 4 + uvCount][:-1].split(" ")
        for j in range( len(weightId) ):
            weights.append( [ int(weightId[j]), float(weight[j]) ] )
    else:
        weights  = False
    return [vertexs, normals, colors, uvs, weights ]

def createMaterial(materialName, path, format, textureList, suffix):
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

        if suffix:
            for h in range(len(suffix)):
                length = len(suffix[h]) * -1
                for i in textureList:
                    if i[0][length:] == suffix[h]:
                        texture = i[0]
                        nodeConfig                            = mat.node_tree.nodes.new('ShaderNodeTexImage')
                        nodeConfig.hide                       = True
                        nodeConfig.width                      = 0.0
                        nodeConfig.interpolation              = 'Closest'
                        if bpy.data.images.get(i[0]+format) is None:
                            pathTo = ""
                            if os.path.isfile(path+"\\"+texture+format):
                                pathTo           = path+"\\"+texture+format
                                nodeConfig.image = bpy.data.images.load(pathTo)
                            else:
                                print("Could't find",path+"\\"+texture+format)
                        else:
                            nodeConfig.image = bpy.data.images.get(texture+format)

                        if nodeConfig.image:
                            if h == 0: # Base Color
                                nodeConfig.location  = (-70, 130)
                                mat.node_tree.links.new(bsdf.inputs['Base Color'], nodeConfig.outputs['Color'])
                            elif h == 1: # Normal
                                normalMap            = mat.node_tree.nodes.new('ShaderNodeNormalMap')
                                normalMap.hide       = True
                                normalMap.space      = 'BLENDER_WORLD'
                                normalMap.location   = (-70, -150)
                                normalMap.inputs[0].default_value = 0.6
                                nodeConfig.location  = (-370, -150)
                                mat.node_tree.links.new(normalMap.inputs['Color'],     nodeConfig.outputs['Color'])
                                mat.node_tree.links.new(bsdf.inputs['Normal'],     normalMap.outputs['Normal'])
                            elif h == 2: # Metallic
                                nodeConfig.location  = (-120, 90)
                                mat.node_tree.links.new(bsdf.inputs['Metallic'],   nodeConfig.outputs['Color'])
                            elif h == 3: # Opacity
                                nodeConfig.location  = (-120, -110)
                                mat.node_tree.links.new(bsdf.inputs['Alpha'],      nodeConfig.outputs['Color'])
                        break

        else:
            texBaseColor                            = mat.node_tree.nodes.new('ShaderNodeTexImage')
            texBaseColor.hide                       = True
            texBaseColor.width                      = 0.0
            texBaseColor.location                   = (-49, 157)
            texBaseColor.interpolation              = 'Closest'
            if bpy.data.images.get(textureList[0][0]+format) is None:
                pathTo = ""
                if os.path.isfile(path+"\\"+textureList[0][0]+format):
                    pathTo           = path+"\\"+textureList[0][0]+format
                    texBaseColor.image = bpy.data.images.load(pathTo)
                else:
                    print("Could't find",path+"\\"+textureList[0][0]+format)
            else:
                texBaseColor.image = bpy.data.images.get(textureList[0][0]+format)
            mat.node_tree.links.new(bsdf.inputs['Base Color'], texBaseColor.outputs['Color'])
    return mat

def readASCII280(context, f, collect, fileName, upAxis, scale, loadSkel, loadNormal, loadVrtxClr, loadUv, format, path, suffix):
    # SKELETON
    boneCount = int(f[0])
    if boneCount != 0 and loadSkel:
        skl    = bpy.data.objects.new(fileName, bpy.data.armatures.new("arm_"+fileName))
        skl.data.display_type = "STICK"
        collect.objects.link(skl)
        bpy.context.view_layer.objects.active = skl

        boneList = []
        bpy.ops.object.mode_set(mode='EDIT')
        for h in range(boneCount):
            name        = f[h * 3 + 1][:-1]
            parent      = int(f[h * 3 + 2])
            coords      = f[h * 3 + 3][:-1].split(" ")
            quat        = mathutils.Quaternion([float(coords[6]), float(coords[3]), float(coords[4]), float(coords[5])]).to_matrix().to_4x4()
            if upAxis == "0":
                locate  = [float(coords[0])/scale, float(coords[1])/scale, float(coords[2])/scale]
            else:
                locate  = [float(coords[2])/scale, float(coords[0])/scale, float(coords[1])/scale]
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
        mesh         = bpy.data.meshes.new("pol_" + str(h).zfill(2))
        uvCount      = int(f[currentLine+1])
        textureCount = int(f[currentLine+2])
        textureList  = []
        for i in range(textureCount):
            textureName = f[currentLine + 3 + i*2 + 0 ][:-1].split(".")[0]
            unkn        = f[currentLine + 3 + i*2 + 1 ][:-1]
            textureList.append( [textureName, unkn] )
        mat     = createMaterial( "material_"+str(h).zfill(3), path, format, textureList, suffix )
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
            values   = readData(f, vertexLine + i * linesPerVertex, uvCount, boneCount, upAxis, scale, loadNormal, loadVrtxClr, loadUv)
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

        # UV's
        if loadUv:
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
        if loadVrtxClr:
            color_layer  = bm.loops.layers.color.new()
            for i in bm.faces:
                i.loops[0][color_layer] = (vColors[faces[i.index][0]])
                i.loops[1][color_layer] = (vColors[faces[i.index][1]])
                i.loops[2][color_layer] = (vColors[faces[i.index][2]])

        # Weights
        if boneCount != 0 and loadSkel:
            weight_layer = bm.verts.layers.deform.new()
            orderBones = []
            for i in bm.verts:
                for j in weights[i.index]:
                    if not j[0] in orderBones:
                        orderBones.append(j[0])
                        object.vertex_groups.new(name=boneList[j[0]])
                    i[weight_layer][orderBones.index(j[0])] = j[1]

            object.modifiers.new(name="mod_" + str(h).zfill(2), type="ARMATURE")
            object.modifiers["mod_" + str(h).zfill(2)].object  = skl
            object.parent = skl

        bm.to_mesh(mesh)
        bm.free()

        # Normals
        if loadNormal:
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
        min=0.0,
        soft_min=0.0,
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
        default=True,
    )

    loadUV: BoolProperty(
        name="Load UV",
        description="Load all object UV channels or ignore them\nDisable isn't recommended but faster",
        default=True,
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
        default="../textures/",
    )

    sColor: StringProperty(
        name="Base Color / Diffuse suffix",
        description="Base color or diffuse texture",
        default="_C",
    )

    sNormal: StringProperty(
        name="Normal suffix",
        description="Normal texture",
        default="_N",
    )

    sMetallic: StringProperty(
        name="Metallic suffix",
        description="Metallic texture",
        default="_M",
    )

    sOpacity: StringProperty(
        name="Opacity suffix",
        description="Useful when texture path isn't in the same place as model file",
        default="_O",
    )

    sAmbientOcclusion: StringProperty(
        name="Ambient Occlusion suffix",
        description="Useful when texture path isn't in the same place as model file",
        default="",
    )

    sRoughness: StringProperty(
        name="Roughness suffix",
        description="Useful when texture path isn't in the same place as model file",
        default="",
    )

    sSpecular: StringProperty(
        name="Specular suffix",
        description="Useful when texture path isn't in the same place as model file",
        default="",
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
            for i in bpy.data.objects:
                bpy.data.objects.remove(i)
            for i in bpy.data.meshes:
                bpy.data.meshes.remove(i)
            for i in bpy.data.lights:
                bpy.data.lights.remove(i)
            for i in bpy.data.materials:
                bpy.data.materials.remove(i)
            for i in bpy.data.images:
                bpy.data.images.remove(i)
            for i in bpy.data.collections:
                bpy.data.collections.remove(i)
        startScript = time.time()
        directory    = self.directory
        scale        = self.scale
        loadSkeleton = self.loadSkeleton
        loadNormal   = self.loadNormal
        loadVertxClr = self.loadVertexColor
        loadUV       = self.loadUV
        texturePath  = self.texturePath if self.texturePath[1] == ":" else os.path.abspath(directory+self.texturePath)
        print("Configuration")
        print("  Up axis:        Original" if self.upAxis == "0" else "  Up axis:        Change")
        print("  Scale:          Original" if scale == 1         else "  Scale:          "+str(scale))
        print("  Skeleton:       Original" if loadSkeleton       else "  Skeleton:       Skip")
        print("  Normals:        Original" if loadNormal         else "  Normals:        Skip")
        print("  Vertex Colors:  Original" if loadVertxClr       else "  Vertex Colors:  Skip")
        print("  UV coords:      Original" if loadUV             else "  UV coords:      Skip")
        print("  Join objects:   Yes"      if self.joinObj       else "  Join objects:   No")
        print("  Texture format:",self.textureFormat)
        print("  Texture path:  ",texturePath)
        print("================")

        for file_elem in self.files:
            file      = directory+file_elem.name
            fileName  = bpy.path.basename(file)
            fileExtn  = fileName.split(".")[-1]
            fileName  = fileName.split(".")[0]
            binfile   = open(file, 'r').readlines()

            print(" ",fileName)
            start_time = time.time()
            if fileExtn == "ascii":
                if bpy.data.collections.get("ascii_"+fileName) is not None:
                    collect = bpy.data.collections.get("ascii_"+fileName)
                else:
                    collect  = bpy.data.collections.new("ascii_"+fileName)
                    bpy.context.scene.collection.children.link( collect )
                if self.sColor or self.sNormal or self.sMetallic or self.sOpacity or self.sAmbientOcclusion or self.sRoughness or self.sSpecular:
                    suffix = [self.sColor, self.sNormal, self.sMetallic, self.sOpacity, self.sAmbientOcclusion, self.sRoughness, self.sSpecular]
                else:
                    suffix = False
                readASCII280(context, binfile, collect, fileName, self.upAxis, scale, loadSkeleton, loadNormal, loadVertxClr, loadUV, self.textureFormat, texturePath, suffix)

                if self.joinObj:
                    isTheFirstOne = True
                    for obj in bpy.data.collections["ascii_"+fileName].all_objects:
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
