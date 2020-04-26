"""
AerialWareQGISIntegration
Copyright (C) 2020 matafokka

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

"""

from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QMessageBox
from PyQt5.QtCore import QSize, QVariant
from qgis.core import QgsMapLayerType, QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject, QgsField
from os import path
import importlib.util
import sys

class DummyWidget(QWidget):
	project = QgsProject.instance()

	def __init__(self):
		super().__init__()
		
		# Load layers
		layers, layersList, layersDict = self.project.mapLayers(), [], {}
		# If there are no raster layers, raise an error message
		if len(layers) == 0:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Critical)
			msg.setWindowTitle("No raster layer opened")
			msg.setText("Sorry, but AerialWare works with raster layers only. Please, load at least one raster layer and try again.")
			msg.exec_()
			return
		
		# Parse layers
		for id in layers:
			layer = layers[id]
			if layer.type() != QgsMapLayerType.RasterLayer: continue
			name = layer.name()
			layersList.append(name)
			layersDict[name] = layer
		
		# Import AerialWare
		if not self.onStart():
			self.deleteLater()
			return
		
		# Create window that asks user to choose a layer to work with
		name = QInputDialog.getItem(self, "Select layer", "Please, select a layer to work with:", layersList)
		if not name[1]: return
		layer = layersDict[name[0]]
		
		# Load AerialWare
		self.aw = sys.modules["AerialWare"].AerialWareWidget(True)
		self.aw.loadImageFromQImage(layer.previewAsImage(
			QSize(layer.width(), layer.height())
		))
		self.aw.show()
		self.aw.done.connect(self.onEnd)
	
	def onStart(self):
		"""Does everything to import AerialWare.
		Returns:
			True - if successfuly imported
			False - otherwise
		"""
		# Try to import from default directory
		try:
			from AerialWare import AerialWare
			return True
		except: pass
		
		# Try to read directory from file and import from it
		file = open("AerialWarePath.txt", "w")
		imported = False
		try:
			imported = self.importAerialWare(file.readline())
		except: pass
		
		if imported:
			file.close()
			return True
		
		# Ask user for directory
		path = ""
		while True:
			pathToAerialWare = QInputDialog.getText(self, "Path to AerialWare", "Please, write path to AerialWare folder:")
			if not pathToAerialWare[1]:
				file.close()
				return False
			path = pathToAerialWare[0]
			if not self.importAerialWare(path): continue
			break
		
		file.write(path)
		file.close()
		
		return True

	def importAerialWare(self, pathToAerialWare: str):
		"""Tries to import AerialWare from given path.
		Returns:
			True - if successfuly imported
			False - otherwise
		"""
		try:
			spec = importlib.util.spec_from_file_location("AerialWare", path.normpath(pathToAerialWare + "/AerialWare.py"))
			awModule = importlib.util.module_from_spec(spec)
			sys.modules["AerialWare"] = awModule
			spec.loader.exec_module(awModule)
		except Exception as e: return False
		return True

	def onEnd(self):
		"""Does all the stuff when user is done with AerialWare
		"""
		self.makeLayer(self.aw.getPathByMeridiansLinesWithTurnsDeg(), "Meridians")
		self.makeLayer(self.aw.getPathByHorizontalsLinesWithTurnsDeg(), "Horizontals")
		self.aw.close()
		self.aw.deleteLater()
		self.deleteLater()

	def makeLayer(self, lines, name):
		"""Creates a layer with polyline from given points
		"""
		height = self.aw.getFlightHeight()
		
		# Create first point and add it to the list
		p = QgsPoint(lines[0].p1())
		p.addMValue(height)
		points = [p]
		
		# Add each second point (because first point of each line is equal to the first point of a previous line) to the list
		for line in lines:
			p = QgsPoint(line.p2())
			p.addMValue(height)
			points.append(p)
		
		# Create a polyline feature from points
		feature = QgsFeature()
		feature.setGeometry(QgsGeometry.fromPolyline(points))
		
		# Define attributes
		attrs = [
			QgsField("max_area_to_capture_height", QVariant.Double),
			QgsField("max_area_to_capture_width", QVariant.Double),
			QgsField("meters_in_pixel_ratio", QVariant.Double),
			QgsField("resolution_height", QVariant.Int),
			QgsField("resolution_width", QVariant.Int),
			QgsField("camera_focal_length", QVariant.Double)
		]
		
		# Fill feature's fields with these attributes
		fields = QgsFields()
		for field in attrs:
			fields.append(field)
		feature.setFields(fields)
		
		# Assign values to the attributes
		area = self.aw.getMaxArea()
		res = self.aw.getCameraResolution()
		feature.setAttribute("max_area_to_capture_height", area["h"])
		feature.setAttribute("max_area_to_capture_width", area["w"])
		feature.setAttribute("meters_in_pixel_ratio", self.aw.getCameraRatio())
		feature.setAttribute("resolution_height", res["h"])
		feature.setAttribute("resolution_width", res["w"])
		feature.setAttribute("camera_focal_length", self.aw.getFocalLength())
		
		# Create a vector layer
		layer = QgsVectorLayer("LineString?crs=epsg:4326", name, "memory")
		provider = layer.dataProvider()
		layer.startEditing()
		
		provider.addAttributes(attrs)
		layer.updateFields()
		
		provider.addFeatures([feature])
		
		layer.commitChanges()
		layer.updateExtents()
		
		# Add layer to the map
		self.project.addMapLayer(layer)

w = DummyWidget()