#!/usr/bin/env python

import freenect
import numpy
import scipy
import scipy.ndimage

class PlyWriter(object):
    def __init__(self,name):
        self.name =  name
        
    def save(self,array,depth):
        points = []
        points.extend(self.mesh_points(array))
        if depth:
            points.extend(self.outline_points(array,depth))
            points.extend(self.back_points(array,depth))
        
        f = open(self.name,'w')
        
        self.write_header(f,points)
        self.write_points(f,points)
        
        f.close()
        
    # inspired by, but not based on http://borglabs.com/blog/create-point-clouds-from-kinect
    def mesh_points(self,array):
        points = []
        
        # depth approximation from ROS, in mm
        array = (array != 0) * 1000.0/(-0.00307 * array + 3.33)
        
        dims = array.shape
        minDistance = -100
        scaleFactor = 0.0021
        ratio = float(dims[0])/float(dims[1])
        
        for i in range(0,dims[0]):
            for j in range(0,dims[1]):
                z = array[i,j]
                if z:
                    # from http://openkinect.org/wiki/Imaging_Information
                    x = float(i - dims[0] / 2) * float(z + minDistance) * scaleFactor * ratio
                    y = float(j - dims[1] / 2) * float(z + minDistance) * scaleFactor
                    points.append('%f %f %f\n' % (x,y,z))
                    
        return points
                    
    def outline_points(self,array,depth):

        points = []
        return points
        
    def back_points(self,array,depth):
        
        return self.mesh_points(array)
        
    def write_header(self,f,points):
        f.write('ply\n')
        f.write('format ascii 1.0\n')
        f.write('element vertex %d\n' % len(points))
        f.write('property float x\n')
        f.write('property float y\n')
        f.write('property float z\n')
        f.write('end_header\n')
        
    def write_points(self,f,points):
        f.writelines(points)
        

class FaceCube(object):
    def __init__(self):
        self.depth, timestamp = freenect.sync_get_depth()
        self.threshold = None
        self.segmented = None
        self.selected_segment = None
        pass
    
    def update(self):
        self.depth, timestamp = freenect.sync_get_depth()
        
    def generate_threshold(self, face_depth):
        # the image breaks down when you get too close, so cap it at around 60cm
        self.depth = self.depth + 2047 * (self.depth <= 544)
        closest = numpy.amin(self.depth)
        closest_cm = 100.0/(-0.00307 * closest + 3.33)
        farthest = (100/(closest_cm + face_depth) - 3.33)/-0.00307
        hist, bins = numpy.histogram(self.depth)
        self.threshold = self.depth * (self.depth <= farthest)
    
    def select_segment(self,point):
        segments, num_segments = scipy.ndimage.measurements.label(self.threshold)
        selected = segments[point[1],point[0]]
        
        if selected:
            self.selected_segment = (point[1],point[0])
        else:
            self.selected_segment = None
            self.segmented = None
    
    def segment(self):
        if self.selected_segment != None:
            segments, num_segments = scipy.ndimage.measurements.label(self.threshold)
            selected = segments[self.selected_segment]
            if selected:
                self.segmented = self.threshold * (segments == selected)
            else:
                self.segmented = None
        
    def hole_fill(self,window):
        if self.segmented != None:
            self.segmented = scipy.ndimage.morphology.grey_closing(self.segmented,size=(window,window))
            
    def get_array(self):
        if self.segmented != None:
            return self.segmented
        else:
            return self.threshold
        
if __name__ == '__main__':
    import pygame
    from pygame.locals import *

    size = (640, 480)
    pygame.init()
    display = pygame.display.set_mode(size, 0)
    face_depth = 10.0
    facecube = FaceCube()
    going = True
    capturing = True
    hole_filling = 0
    changing_depth = 0.0
    filename = 'test.ply'
    
    while going:
        events = pygame.event.get()
        for e in events:
            if e.type == QUIT or (e.type == KEYDOWN and e.key == K_ESCAPE):
                going = False
                
            elif e.type == KEYDOWN:
                if e.key == K_UP:
                    changing_depth = 1.0
                elif e.key == K_DOWN:
                    changing_depth = -1.0
                elif e.key == K_SPACE:
                    capturing = not capturing
                elif e.key == K_h:
                    hole_filling += 1
                    print "Hole filling window set to %d" % hole_filling
                elif e.key == K_g:
                    hole_filling = max(0,hole_filling-1)
                    print "Hole filling window set to %d" % hole_filling
                elif e.key == K_s:
                    print "Saving array as %s" % filename
                    writer = PlyWriter(filename)
                    writer.save(facecube.get_array(),face_depth)
                    
            elif e.type == KEYUP:
                if changing_depth != 0.0:
                    changing_depth = 0.0
                    print "Getting closest %d cm" % face_depth
                    
            elif e.type == MOUSEBUTTONDOWN:
                facecube.select_segment(pygame.mouse.get_pos())
                
        if capturing:
            facecube.update()
        
        face_depth = min(max(0.0,face_depth + changing_depth),2047.0)
        
        facecube.generate_threshold(face_depth)
        facecube.segment()
        if hole_filling:
            facecube.hole_fill(hole_filling)
        
        # this is not actually correct, but it sure does look cool!
        display.blit(pygame.surfarray.make_surface(facecube.get_array().transpose()),(0,0))
        pygame.display.flip()
