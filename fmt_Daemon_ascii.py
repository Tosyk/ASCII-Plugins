from inc_noesis import *
import noesis
import rapi

def registerNoesisTypes():
	handle = noesis.register("ID-Daemon Model", ".ascii")
	noesis.setHandlerTypeCheck(handle, noeCheckGeneric)
	noesis.setHandlerLoadModel(handle, mdlLoadModel)
	return 1

def mdlLoadModel(data, mdlList):
	ctx = rapi.rpgCreateContext()
	fileName = rapi.getExtensionlessName(rapi.getLocalFileName(rapi.getLastCheckedName()))
	filePath = rapi.getDirForFilePath(rapi.getLastCheckedName())
	model = asciiFile(NoeBitStream(data), fileName, filePath)
	try:
		mdl = rapi.rpgConstructModel()
	except:
		mdl = NoeModel()
	mdl.setModelMaterials(NoeModelMaterials(model.texList, model.matList))
	mdlList.append(mdl); mdl.setBones(model.boneList)	
	return 1

class asciiFile: 
	
	def __init__(self, bs, fileName, filePath):
		self.texList = []
		self.matList = []
		self.matDict = {}
		self.boneList = []
		self.boneMap = []
		self.boneDict = {}
		self.fileName = fileName
		self.filePath = filePath
		self.loadAll(bs)
		
	def loadAll(self, bs):
		boneCount = strToInt(readLine(bs))
		self.readBones(bs, boneCount)
		meshCount = strToInt(readLine(bs))
		for i in range(meshCount):
			self.readMesh(bs, boneCount)

	def readBones(self, bs, boneCount):
		for i in range(boneCount):
			boneName = readLine(bs)
			parent = strToInt(readLine(bs))
			boneData = readLine(bs).split()
			if len(boneData) > 3:
				boneMtx = NoeQuat((float(boneData[3]), float(boneData[4]), float(boneData[5]), float(boneData[6]))).toMat43()
			else:
				boneMtx = NoeMat43()
			boneMtx[3] = NoeVec3((float(boneData[0]), float(boneData[1]), float(boneData[2])))
			newBone = NoeBone(i, boneName, boneMtx, None, parent)
			self.boneList.append(newBone)

	def readMesh(self, bs, boneCount):
		meshName = parseStr(readLine(bs))
		uvCount = strToInt(readLine(bs))
		texCount = strToInt(readLine(bs))
		material = NoeMaterial(meshName, "")
		for i in range(texCount):
			tex = parseStr(readLine(bs))
			layerIdx = strToInt(readLine(bs))
		self.matList.append(material)
		vertCount = strToInt(readLine(bs))
		vertList = []
		normList = []
		colourList = []
		uvList = [[] for x in range(uvCount)]
		indexList = []
		weightList = []
		stride = 0
		for i in range(vertCount):
			vert = strToVec(readLine(bs))
			vertList.extend([float(vert[0]), float(vert[1]), float(vert[2])])
			norm = strToVec(readLine(bs))
			normList.extend([float(norm[0]), float(norm[1]), float(norm[2])])
			col = strToVec(readLine(bs))
			colourList.extend([int(col[0]), int(col[1]), int(col[2]), int(col[3])])
			for a in range(uvCount):
				uv = strToVec(readLine(bs))
				uvList[a].extend([float(uv[0]), float(uv[1])])
			if boneCount > 0:
				ind = strToVec(readLine(bs))
				wght = strToVec(readLine(bs))
				if i == 0:
					stride = len(wght)
				for a in range(stride):
					indexList.append(int(ind[a]))
					weightList.append(float(wght[a]))
		faceCount = strToInt(readLine(bs))
		faceList = []
		for i in range(faceCount):
			face = strToVec(readLine(bs))
			faceList.extend([int(face[0]), int(face[2]), int(face[1])])
		rapi.rpgSetName(meshName)
		rapi.rpgSetMaterial(meshName)
		rapi.rpgBindPositionBuffer(struct.pack('f'*len(vertList), *vertList), noesis.RPGEODATA_FLOAT, 12)
		rapi.rpgBindNormalBuffer(struct.pack('f'*len(normList), *normList), noesis.RPGEODATA_FLOAT, 12)
		rapi.rpgBindColorBuffer(struct.pack('I'*len(colourList), *colourList), noesis.RPGEODATA_UINT, 16, 4)
		for i in range(uvCount):
			if i == 0:
				rapi.rpgBindUV1Buffer(struct.pack('f'*len(uvList[i]), *uvList[i]), noesis.RPGEODATA_FLOAT, 8)
			elif i == 1:
				rapi.rpgBindUV2Buffer(struct.pack('f'*len(uvList[i]), *uvList[i]), noesis.RPGEODATA_FLOAT, 8)
			else:
				rapi.rpgBindUVXBuffer(struct.pack('f'*len(uvList[i]), *uvList[i]), noesis.RPGEODATA_FLOAT, 8, i, 2)
		if stride != 0:
			rapi.rpgBindBoneIndexBuffer(struct.pack('I'*len(indexList), *indexList), noesis.RPGEODATA_UINT, stride * 4, stride)
			rapi.rpgBindBoneWeightBuffer(struct.pack('f'*len(weightList), *weightList), noesis.RPGEODATA_FLOAT, stride * 4, stride)
		rapi.rpgCommitTriangles(struct.pack('I'*len(faceList), *faceList), noesis.RPGEODATA_UINT, faceCount * 3, noesis.RPGEO_TRIANGLE, 1)
		rapi.rpgClearBufferBinds()

def parseStr(string):
	str = string.split(' ')
	return str[0]
	
def strToInt(str):
	return int(parseStr(str))

def strToFloat(str):
	return float(parseStr(str))

def strToVec(str):
	return str.split(' ')
	
def trim(s):
	if s != '':
		if s[len(s) - 1] == ' ':
			s = s[:len(s)-1]
		if s[0] == ' ':
			s = s[1:]
	return s
	
def readLine(bs):
	ret = bs.readline().split('\r')
	ret = ret[0].split('\n')
	ret[0] = trim(ret[0])
	return ret[0]