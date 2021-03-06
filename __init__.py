# -*- coding: utf-8 -*-
"""
Created on Wed May  4 10:33:14 2016

@author: Jeremy Nowell and Gordon Gibb
"""
from __future__ import print_function

import Queue
from threading import Thread
import subprocess
import time
import os
import chimera
import stat

WORKING_DIR = '/Users/ggibb2/Projects/CP2K'
WORKING_DIR= '/Users/ggibb2/Projects/CP2K/tetr_4.97'
ROOT_DIR='/Users/ggibb2/Projects/CP2K/tetr_4.97'

home=os.path.expanduser("~")
#tetrdir=home+"/.Tetr"
#axisfile=tetrdir+"/axis.bild"
#latticefile=tetrdir+"/lattice.bild"

#modelno = 5 #xyz number
cubeno = 500 #cube number
axisno = 600 #axis number
latticeno=700



def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()
    
    
def parse_list(list):
    #Takes a list of numbers and formats a string to present the list so that:
    # 1,2,3,4,5,8,10,15,16,17
    # becomes
    # 1-5 8 10 15-17

    # It compares the ith element to (i-1)th element in list. If they are contiguous 
    # (i.e. 11 and 12) then it skips to the next element pair. If not,
    # it prints the last contiguous range
    
    #sort the incoming list
    list.sort() 

    #string to put the range into
    string="" 

    #start value of initial contiguous range (first element of list)
    start=list[0]

    #number of elements in list
    end=len(list)

    #loop over every element in list (also include an extra iteration at the end as it
    # prints out the i-1th element, so need to go to end+1 to include the last element)
    for i in range(len(list)+1):
        
        #skip first element as cannot compare 0th and -1th elements
        if i==0:
            continue
        
        #calculate difference in ith and (i-1)th element
        if i!= end:
            diff=list[i]-list[i-1]
        else:
            diff=-1
        
        #if the difference is not one (they are NOT contiguous)
        if diff != 1:
            
            #the previous contiguous set ends at the (i-1)th element
            stop=list[i-1]
            
            #print out the previous contiguous chunk
            if (stop == start): #only a single number in this range
                string = string + str(start) + " "
            else: #prints out range in form start-stop
                string=string+str(start)+"-"+str(stop)+" "
            
            #define start value of new contiguous range
            if i!= end:
                start=list[i]
        
    return string


class LevApp():
    def __init__(self,rootdir=ROOT_DIR,wkdir=WORKING_DIR):
        
        self.geomProp = time.time()
        
        self.model=None #will contain a reference to the model object in chimera
        self.oldmodel=None #will contain the previous model opened (retain it so its view settings can be copied to the new model)
        self.om=chimera.openModels #object containing information on open models
        self.style=0 #default starting style
        self.axis=None
        self.lattice=None
        
        self.cube= None
        
        self.wkdir=wkdir
        
       
        self.IsOpen=False
        
        self.outQueue = Queue.Queue()
        self.outThread = Thread(target=enqueue_output,
                           args=(self.Proc.stdout, self.outQueue))
        self.outThread.daemon = True
        self.outThread.start()
       
        


    def getOutput(self):
        print("getOutput")
        outStr = ''
        try:
            while True: #Adds output from the Queue until it is empty
                outStr += self.outQueue.get_nowait()

        except Queue.Empty:
            print("no more output")
            #print(outStr)
            return outStr

    def setInput(self, inStr):
        print("setInput")
        print(inStr)
        print("LENGTH OF INPUTTED STRING=",len(inStr))
        self.Proc.stdin.write(inStr + "\n")

                
    def refreshGeom(self,force=False): #reloads the model (if the file has changed)
        geomFile=self._getGeomPath(self.geomfile)
        if (os.path.isfile(geomFile)):
            mTime = os.stat(geomFile).st_mtime
            if mTime > self.geomProp: #if the file has changed since it was last opened
                self.geomProp = mTime
                self.openGeom(geomFile) #open the new file
            elif force:
                self.openGeom(geomFile) #open the new file
                    
    def openGeom(self,geomFile):
        #geomFile=self._getGeomPath()
        
        self.oldmodel=self.model
        
        xf=None
        
        
        #try to close files
        if self.oldmodel !=None:
            print("Transferring information from old to new model")
            try:
                xf=self.oldmodel.openState.xform #save transform matrix
                self.om.close(self.oldmodel)
                self.oldmodel=None
            except:
                try:
                    self.om.close(self.oldmodel)
                except:
                    pass
            self.oldmodel=None
        
        print("Opening ",geomFile)
        self.om.open(geomFile,baseId=self.modelno) #reads the file, associating it with model number self.modelno
        self.model=self.getModel(self.modelno) #obtain a handle to the model
            
        if xf != None:
            self.model.openState.xform=xf
            #mc.molecule_copy(self.oldmodel.atoms,self.model.atoms)
            
        self.UpdateView()
        
                
    def getModel(self,number): #obtains the .xyz model object (model number self.modelno)
        modlist = self.om.list() #get list of models
        modlist.reverse() #reverses the order of modlist (as the newer model is appended after the previous model)
        for model in modlist:
            if model.id == number:
                return model
        return None
    
    
    def GetSelection(self): #gets the list of selected atoms in chimera and returns a string suitable for passing into tetr's "T" option.
        print("Getting Selection")
        atoms=chimera.selection.currentAtoms()
        list=[]
        for atom in atoms:
            list.append(atom.coordIndex+1)
        if (len(list) > 0):    
            print(len(list)," atoms in selection")
            string=parse_list(list)
        else:
            print("no atoms in selection")
            string=None
        
        return string
    
    def SetSelection(self,nums):
        sel=chimera.selection
        
        #clear any previous selection
        
        sel.clearCurrent()
        
        
        #construct atom list from numbers
        atomlist=[]
        
        atoms=self.model.atoms
        
        for n in nums:
            atomlist.append(atoms[n-1])
        
        sel.setCurrent(atomlist)
        
        
        
        
    
    #gets view option from GUI (opt) and gets chimera to change the view
    def SetViewOption(self,opt):
        self.style=opt
        self.UpdateView()
        
    def UpdateView(self):
        style=self.style
        
        if style==0:
            atomMode=chimera.Atom.EndCap
            bondMode=chimera.Bond.Stick
        elif style==1:
            atomMode = chimera.Atom.Ball
            bondMode = chimera.Bond.Stick
        elif style==2:
            atomMode = chimera.Atom.Dot
            bondMode = chimera.Bond.Wire
        elif style==3:
            atomMode = chimera.Atom.Sphere
            bondMode = chimera.Bond.Wire
        
        #loop over atoms and bonds and apply view options
        if self.model != None:
            for atom in self.model.atoms:
                atom.drawMode=atomMode
            for bond in chimera.misc.bonds(self.model.atoms, internal=True):
                bond.drawMode = bondMode
                
    def UpdateLabels(self,num,species):
        if self.model != None:
            for atom in self.model.atoms:
                label=""
                if species == 1:
                    label+=atom.element.name
                if num == 1:
                    label+=str(atom.coordIndex +1)
                atom.label=label
        
        
    def ShowAxis(self,toggle):
        if toggle==False:
            print("Axis off")
            if self.axis != None:
                self.om.close(self.axis)
                self.axis=None
        else:
            print("Axis on")
            if self.axis != None:
                self.om.close(self.axis)
            self.om.open(self.axisfile,baseId=axisno)
            self.axis=self.getModel(axisno)
            
    def ShowLattice(self,toggle):
        if toggle==False:
            print("Lattice Off")
            if self.lattice!=None:
                self.om.close(self.lattice)
                self.lattice=None
        else:
            print("Lattice on")
            if self.lattice != None:
                self.om.close(self.lattice)
            self.om.open(self.latticefile,baseId=latticeno)
            self.lattice=self.getModel(latticeno)
    
    
    def CloseModels(self):
        if self.model != None:
            self.om.close(self.model)
        if self.axis != None:
            self.om.close(self.axis)
        if self.lattice != None:
            self.om.close(self.lattice)
        if self.cube != None:
            self.om.close(self.cube)

    
    def _getGeomPath(self,file):
        return os.path.join(self.wkdir, file)
    
    def getCubePath(self):
        return os.path.join(self.wkdir, self.cubefile)


class Tetr(LevApp):
    def __init__(self,rootdir,wkdir,myshell="/bin/bash"):
        
        print("INITIALISING TETR")
       
       
        tetrdir=home+"/.Tetr"
        
        str=rootdir+"/tetr CHIMERA=.TRUE."
        print("Command to run=",str)
        
        
        f=open(tetrdir+"/run.sh","w")
        
        if myshell=="/bin/bash" or myshell == "/bin/sh":
            f.write("#!"+myshell+" -login\n")
        else:
            f.write("#!"+myshell+"\n")
        f.write(str)
        f.close()
        
        st = os.stat(tetrdir+"/run.sh")
        os.chmod(tetrdir+"/run.sh", st.st_mode | stat.S_IEXEC)
        
        
        self.Proc = subprocess.Popen([tetrdir+"/run.sh"],
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         shell=True,
                                         executable=myshell,
                                         universal_newlines=True,
                                         cwd=wkdir,
                                         env=dict(os.environ, HOME_TETR=rootdir))
        
        
        self.axisfile=tetrdir+"/axis.bild"
        self.latticefile=tetrdir+"/lattice.bild"
        
        self.geomfile='geom.xyz' #file to be opened
        
        self.modelno=5
        
        LevApp.__init__(self,rootdir,wkdir)
        
        
        
        
        
        
        
class Lev00(LevApp):
    def __init__(self,rootdir,wkdir,myshell="/bin/bash"):
        
        print("INITIALISING Lev00")
        
        str=rootdir+"/lev00 CHIMERA=TRUE"
        print("Command to run=",str)
        
        lev00dir=home+"/.Lev00"
        
        f=open(lev00dir+"/run.sh","w")
        
        if myshell=="/bin/bash" or myshell == "/bin/sh":
            f.write("#!"+myshell+" -login\n")
        else:
            f.write("#!"+myshell+"\n")
        f.write(str)
        f.close()
        
        st = os.stat(lev00dir+"/run.sh")
        os.chmod(lev00dir+"/run.sh", st.st_mode | stat.S_IEXEC)
       
        
        self.Proc = subprocess.Popen(lev00dir+"/run.sh",
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         shell=True,
                                         executable=myshell,
                                         universal_newlines=True,
                                         cwd=wkdir)#,
                                        # env=dict(os.environ))
        
        
        self.axisfile=lev00dir+"/axis.bild"
        self.latticefile=lev00dir+"/lattice.bild"
        
        self.geomfile="geom.xyz"
        
        self.cubeprop=time.time()
        self.cubegeomfile="gOpenMol.xyz"
        self.cubefile="gOpenMol.cube"
        
        self.modelno=6
        
        LevApp.__init__(self,rootdir,wkdir)
        
        
    def refreshGeom(self,opt=0,force=False):
        
        if opt==0:
            try:
                self.om.close(self.cube)
            except:
                print("No cube fle to close")
                
            LevApp.refreshGeom(self,force=force)
        else:
            cubeFile=self._getGeomPath(self.cubegeomfile)
            if (os.path.isfile(cubeFile)):
                mTime = os.stat(cubeFile).st_mtime
                if mTime > self.cubeprop: #if the file has changed since it was last opened
                    print("Trying to open cube file")
                    self.cubeprop = mTime
                    self.openGeom(cubeFile,opt=opt) #open the new file
                elif force:
                    self.openGeom(cubeFile,opt=opt) #open the new file
                else:
                    print("Failed to open Cube File")
        
        
        
    def openGeom(self,file,opt=0):
        #run the usual open geom
        LevApp.openGeom(self,file)
        
        #now add bit for the cube files
        
        if self.cube != None:
                self.om.close(self.cube)
        
        if opt==1:
        
            
            
            cubeFile=self.getCubePath()
            
            if (os.path.isfile(cubeFile)):
                self.om.open(cubeFile,baseId=cubeno) #reads the file, associating it with model number self.modelno
                self.cube=self.getModel(cubeno) #obtain a handle to the model
            else:
                print("No cube file to open!")
        

       

