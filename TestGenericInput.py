# Test routines to make sure that our GenericInput class operates properly
# and can interface with dREL

import TransformManager as t
import nx_format_adapter as n
import cif_format_adapter as cf
import CifFile.drel as drel
from CifFile import CifDic
import unittest,os
import numpy,math

class NXAdapterInternalRoutinesTestCase(unittest.TestCase):
    """Test internal utility routines"""
    def setUp(self):
        self.adapter = n.NXAdapter(n.canonical_groupings)
        
    def testTreePartition(self):
        """Test that tree partitioning works correctly"""
        data_1 = ([1,1,1,2,2,2,3,3,3],None)
        data_2 = (['a','b','c','a','b','c','d','e','f'],None)
        data_3 = ([11,22,33,44,55,66,77,88,99],"mm")
        result = self.adapter.create_tree([data_1,data_2,data_3])
        self.failUnless(result[0][2][0]['b']==([55],"mm"))

    def testTreeToArray(self):
        """Test that a key tree is turned back into an array"""
        print 'TreeToArray'
        data_1 = ([1,1,1,1,1,1,2,2,2,2,2,2,3,3,3,3,3,3],None)
        data_2 = (['a','a','b','b','c','c','d','d','e','e','f','f','g','g','h','h','i','i'],None)
        data_3 = ([11,22,33,44,55,66,77,88,99,100,101,102,103,104,105,106,107,108],"mm")
        result = self.adapter.create_tree([data_1,data_2,data_3])
        result_holder = [[],[],[]]
        units_holder = [[],[],[]]
        length,units = self.adapter.synthesize_values(result_holder,result)
        self.failUnless(data_1[0][data_3[0].index(88)]==result_holder[0][result_holder[2].index(88)])
        self.failUnless(data_2[0][data_3[0].index(104)]==result_holder[1][result_holder[2].index(104)])

class NXAdapterWriteReadTestCase(unittest.TestCase):
    """Test round trip read-writing for NXAdapter"""
    def setUp(self):
        self.filename = "ngfulltest.h5"        
        self.adapter = n.NXAdapter(n.canonical_groupings)
        self.adapter.create_data_unit()
        try:
            os.remove(self.filename)
        except OSError:
            print 'Warning: unable to delete ' + `self.filename`

    def reopen(self):
        self.adapter.close_data_unit()
        self.adapter.output_file(self.filename)
        self.adapter.open_file(self.filename)
        print self.adapter.filehandle.tree
        self.adapter.open_data_unit()

    def dump_file(self,filename):
        """Dump a file for debugging"""
        self.adapter.close_data_unit()
        self.adapter.output_file(filename)
        self.setUp()
        self.adapter.open_file(filename)
        print self.adapter.filehandle.tree

    def testGetValue(self):
        """Test that a simple value can be found"""
        self.adapter.set_by_name("incident wavelength",[1.12],"Real","angstroms")
        self.adapter.set_by_name("wavelength id",[1],'Text')
        self.reopen()
        wavelength = self.adapter.get_by_name("incident wavelength","Real","angstroms")
        self.failUnless(abs(wavelength[0] - 1.12) < 0.01)

    def testUnits(self):
        """Test that units are converted correctly"""
        self.adapter.set_by_name("incident wavelength",[1.12],"Real","angstroms")
        self.adapter.set_by_name("wavelength id",[1],'Text')
        self.reopen()
        wavelength = self.adapter.get_by_name("incident wavelength","Real","picometres")
        print 'Wavelength in picometres is ' + `wavelength`
        self.failUnless(abs(wavelength[0] - 0.112) < 0.001)

    def testGetMultiValue(self):
        """Test that a simple multi-valued item can be found"""
        self.adapter.set_by_name("incident wavelength",[1.12,0.85],"Real","angstroms")
        self.adapter.set_by_name("wavelength id",[1,2],'Text')
        self.reopen()
        wavelength = self.adapter.get_by_name("incident wavelength","Real","angstroms")
        self.failUnless(abs(wavelength[0] - 1.12) < 0.01)
        self.failUnless(abs(wavelength[1] - 0.85) < 0.01)

    def testOrderedMultiValue(self):
        """Test that the order is correct for a multi-valued item"""
        self.adapter.set_by_name("incident wavelength",[1.12,0.85],"Real","angstroms")
        self.adapter.set_by_name("wavelength id",[2,1],'Text')
        self.reopen()
        wavelength = self.adapter.get_by_name("incident wavelength","Real","angstroms")
        self.failUnless(abs(wavelength[1] - 1.12) < 0.01)
        self.failUnless(abs(wavelength[0] - 0.85) < 0.01)

    def testGetDataAxis(self):
        """Test that the data axis precedence and names are found"""
        axis_names = ['x','y','phi']
        axis_order = [2,1,3]
        old_dict = dict(zip(axis_names,axis_order))
        self.adapter.set_by_name("data axis precedence",axis_order,"Integer")
        self.adapter.set_by_name("data axis id",axis_names,'Text')
        self.adapter.set_by_name("simple scan data",[[1,2],[3,4],[5,6]],'Integer')
        self.adapter.set_by_name("simple scan frame frame id",[1,2,3],'Integer')
        self.adapter.set_by_name("simple scan frame scan id",['entry1']*3,'Text')
        #self.dump_file('checkfile.h5')
        self.reopen()
        precedence = self.adapter.get_by_name("data axis precedence","Integer")
        new_names = self.adapter.get_by_name("data axis id","Text")
        new_dict = dict(zip(new_names,precedence))
        for k in old_dict.keys():
            self.failUnless(old_dict[k]==new_dict[k])
        
    def testGetAxisNames(self):
        """Test that we can get names that are group IDs"""
        axis_names = ['XPIXEL','YPIXEL','DET_DETECTOR']
        self.adapter.set_by_name('simple detector axis id',axis_names,'Text')
        self.reopen()
        new_axis_names = self.adapter.get_by_name("simple detector axis id","Text")
        self.failUnless(set(new_axis_names).difference(set(axis_names)) == set())
    
    def testGetMoreAxisNames(self):
        """Test that we can get detector axis names"""
        axis_names = ['DETECTOR_X','DETECTOR_Y','STUFF']
        axis_vectors = [[1,2,3],[4,5,6],[3,2,1]]
        old_dict = dict(zip(axis_names,axis_vectors))
        self.adapter.set_by_name("simple detector axis id",axis_names,"Text")
        self.adapter.set_by_name("simple detector axis offset mcstas",axis_vectors,"Real","mm")
        self.reopen()
        new_names = self.adapter.get_by_name("simple detector axis id","Text")
        new_vectors = self.adapter.get_by_name("simple detector axis offset mcstas","Real","cm")
        print "Test: new names, vectors:" + `new_names` + `new_vectors`
        new_dict = dict(zip(new_names,new_vectors))
        for k in old_dict.keys():
            print `new_dict[k]`
            print `0.1*numpy.array(old_dict[k])`
            self.failUnless((numpy.fabs(new_dict[k] - 0.1*numpy.array(old_dict[k]))<0.01).all())
        
    def testNewGroup(self):
        """Test adding an item that is a named group"""
        old_names = ['XPIXEL','YPIXEL','DET_DIST']
        self.adapter.set_by_name("simple detector axis id",old_names,'Text')
        self.reopen()
        new_names = self.adapter.get_by_name("simple detector axis id","Text")
        self.failUnless(set(old_names) == set(new_names))

    def testMultiKeyValue(self):
        """Test that an item is set correctly if it is a key + frameid value"""
        old_names = ['XAXIS','YAXIS','ZAXIS']
        old_vectors = [[1,0,0],[0,1,0],[0,0,1]]
        old_positions = [range(0,10),range(10,0,-1),range(20,30)]
        scan_nos = ['scan1']*30
        # create the actual arrays
        axis_names = []
        [axis_names.extend([a]*10) for a in old_names]
        positions = []
        [positions.extend(a) for a in old_positions]
        frame_nos = range(1,11)*3
        self.adapter.set_by_name("frame axis location angular position",positions,'Real',"degrees")
        self.adapter.set_by_name("frame axis location axis id",axis_names,'Text')
        self.adapter.set_by_name("frame axis location frame id",frame_nos,'Text')
        self.adapter.set_by_name("frame axis location scan id",scan_nos,'Text')
        self.adapter.set_by_name("goniometer axis vector mcstas",old_vectors,'Real')
        self.adapter.set_by_name("goniometer axis id",old_names,'Text')
        self.reopen()
        new_positions = self.adapter.get_by_name("frame axis location angular position",'Real',"radians")
        new_axes = self.adapter.get_by_name("frame axis location axis id","Text")
        new_pos = self.adapter.get_by_name("frame axis location frame id","Text")
        aposindex = positions.index(25)
        print 'New positions: ' + `new_positions`
        newposindex = list(new_positions).index(25*math.pi/180)
        self.failUnless(new_axes[newposindex]==axis_names[aposindex])
        self.failUnless(new_pos[newposindex]=="Frame"+str(frame_nos[aposindex]))

    def testWriteEntryName(self):
        """Test that an entry name is written correctly"""
        self.adapter.set_by_name("incident wavelength",[1.12],"Real","angstroms")
        self.adapter.set_by_name("wavelength id",[1],'Text')
        self.adapter.set_by_name("simple scan frame scan id",['SCAN1'],'Text')
        self.reopen()
        wavelength = self.adapter.get_by_name("incident wavelength","Real","angstroms")
        self.failUnless(abs(wavelength[0] - 1.12) < 0.01)

    def testCompressValues(self):
        """Test that repetitive values are compressed/uncompressed"""
        old_names = ['XAXIS','YAXIS','ZAXIS']
        old_vectors = [[1,0,0],[0,1,0],[0,0,1]]
        old_positions = [range(0,10),[0]*10,[5]*10]
        scan_nos = ['scan1']*30
        # create the actual arrays
        axis_names = []
        [axis_names.extend([a]*10) for a in old_names]
        positions = []
        [positions.extend(a) for a in old_positions]
        frame_nos = range(1,11)*3
        self.adapter.set_by_name("frame axis location angular position",positions,'Real',"degrees")
        self.adapter.set_by_name("frame axis location axis id",axis_names,'Text')
        self.adapter.set_by_name("frame axis location frame id",frame_nos,'Text')
        self.adapter.set_by_name("frame axis location scan id",scan_nos,'Text')
        self.adapter.set_by_name("goniometer axis vector mcstas",old_vectors,'Real')
        self.adapter.set_by_name("goniometer axis id",old_names,'Text')
        self.reopen()
        new_positions = self.adapter.get_by_name("frame axis location angular position",'Real',"radians")
        new_axes = self.adapter.get_by_name("frame axis location axis id","Text")
        new_pos = self.adapter.get_by_name("frame axis location frame id","Text")
        self.failUnless(len(new_axes)==len(new_pos))
        aposindex = positions.index(6)
        print 'New positions: ' + `new_positions`
        newposindex = list(new_positions).index(6*math.pi/180)
        self.failUnless(new_axes[newposindex]==axis_names[aposindex])
        self.failUnless(new_pos[newposindex]=="Frame"+str(frame_nos[aposindex]))

class CifAdapterReadTestCase(unittest.TestCase):
    def setUp(self):
        self.filename = "testfiles/multi-image-test.cif"
        self.adapter = cf.CifAdapter(cf.canonical_name_locations,{})
        self.fh = self.adapter.open_file(self.filename)
        self.adapter.open_data_unit()

    def testGetValue(self):
        """Test that a simple value can be found"""
        wavelength = self.adapter.get_by_name("incident wavelength","Real")
        self.failUnless(abs(wavelength[0]-0.711955)<0.01)

    def testGetImageArray(self):
        """Test that our image reading works correctly"""
        all_frames = self.adapter.get_by_name("2D data","Real")
        self.failUnless(len(all_frames)==5)
        self.failUnless(all_frames[0].shape == (200,300))

class GICifInputTestCase(unittest.TestCase):
    def setUp(self):
        self.dict = CifDic("full_demo_1.0.dic",grammar="2.0",do_dREL=False)
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.cfa.open_file("testfiles/Cu033V2O5_1_001.cbf")
        self.cfa.open_data_unit()
        self.gi = t.GenericInput(self.cfa,self.dict)

    def testPlainInput(self):
        """Test the getitem method"""
        wave = self.gi['_diffrn_radiation_wavelength.wavelength']
        self.failUnless(abs(wave[0]-0.711955)<0.01)

    def testSliceDice(self):
        """Test that we can schedule multiple data units"""
        schedule = self.gi.slice_and_dice(["axis id","detector axis set id"])
        self.failUnless(len(schedule['detector axis set id'])==18)
        self.failUnless(len(schedule['detector axis set id']) == len(schedule['axis id']))
        as_pairs = zip(schedule['detector axis set id'],schedule['axis id'])
        counts = [as_pairs.count(a) for a in as_pairs]
        self.failUnless(max(counts)==1 and min(counts) == 1)

class GIFunctionalityTestCase(unittest.TestCase):
    def setUp(self):
        self.dict = CifDic("full_demo_1.0.dic",grammar="2.0")
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,{})
        self.cfa.open_file("testfiles/multi-image-test.cif")
        self.cfa.open_data_unit()
        self.gi = t.GenericInput(self.cfa,self.dict)

    def testSimpleFilter(self):
        """Test that a simple item is filtered properly"""
        self.gi.add_filter("axis id","ELEMENT_X")
        result = self.gi.get_by_canonical_name("axis id")
        print "Filter result: " + `result`
        self.failUnless(result == ["ELEMENT_X"])

    def testComplexFilter(self):
        """Test that a derived item is filtered properly"""
        self.gi.add_filter("axis id","ELEMENT_X")
        result = self.gi.get_by_canonical_name("simple detector axis id")
        print "Filter result: " + `result`
        self.failUnless(result == ["ELEMENT_X"])

class GITransformToNXTestCase(unittest.TestCase):
    """Testing the dREL transforms using CIF-based input"""
    def setUp(self):
        self.nxa = n.NXAdapter(n.canonical_groupings)
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.nx_filename = 'nx_test_case.h5'
        self.transformer = t.TransformManager()
        self.transformer.register(self.nxa,"nexus")
        self.transformer.register(self.cfa,"cif")
        self.transformer.set_dictionary("full_demo_1.0.dic")
        try:
            os.remove(self.nx_filename)
        except OSError:
            pass

    def check_vals(self,name,value,value_type,tolerance):
        """Check that the given canonical name has the
        stated value"""
        self.nxa.open_file(self.nx_filename)
        self.nxa.open_data_unit()
        new_val = numpy.array(self.nxa.get_by_name(name,value_type))
        if value_type == "Real":
            self.failUnless((abs(new_val-numpy.array(value))<tolerance).all())
        else:
            self.failUnless((new_val == numpy.array(value)).all())

    def dumpfile(self,filename):
        """Dump a file for debugging"""
        self.nxa.open_file(filename)
        print self.nxa.filehandle.tree

    def testPlainTransform(self):
        """Test translation that doesnt need dREL"""
        out_bundle =["incident wavelength","wavelength id"]
        self.transformer.manage_transform(out_bundle,"testfiles/adsc_jrh_testfile.cif","cif",
                                          self.nx_filename,"nexus")
        self.check_vals("incident wavelength",[0.711955],'Real',0.001)

    def testAxisTransform(self):
        """Test that axes are transformed correctly"""
        out_bundle = ["simple detector axis id","simple detector axis vector mcstas","simple detector axis offset mcstas"]
        self.transformer.manage_transform(out_bundle,"testfiles/adsc_jrh_testfile.cif","cif",
                                          "adsc_jrh_testfile.nx","nexus")
        #self.dumpfile(self.nx_filename)
        # create simple array
        self.nxa.open_file("adsc_jrh_testfile.nx")
        self.nxa.open_data_unit()
        new_ids = self.nxa.get_by_name("simple detector axis id","Text")
        new_vecs = self.nxa.get_by_name("simple detector axis vector mcstas","Real")
        new_offsets = self.nxa.get_by_name("simple detector axis offset mcstas","Real")
        check1 = dict(zip(new_ids,new_vecs))
        print 'Test: check1 is ' + `check1`
        self.failUnless((check1['ELEMENT_X']==[-1,0,0]).all())

class GITransformFromNXTestCase(unittest.TestCase):
    """Testing the dREL transforms using NeXus-based input, no output images"""
    def setUp(self):
        self.nxa = n.NXAdapter(n.canonical_groupings)
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.transformer = t.TransformManager()
        self.transformer.register(self.nxa,"nexus")
        self.transformer.register(self.cfa,"cif")
        self.transformer.set_dictionary("full_demo_1.0.dic")
        self.cf_filename = 'cif_test_case.cif'
        try:
            os.remove(self.cf_filename)
        except OSError:
            pass
                  
    def check_vals(self,name,value,value_type,tolerance):
        """Check that the given canonical name has the
        stated value"""
        self.cfa.open_file(self.cf_filename)
        self.cfa.open_data_unit()
        new_val = self.cfa.get_by_name(name,value_type)
        if value_type == "Real":
            self.failUnless((abs(new_val-value)<tolerance).all())
        else:
            self.failUnless((new_val == value).all())

    def testPlainTransform(self):
        """Test translation that doesnt need dREL"""
        out_bundle =  ["wavelength id","incident wavelength"]
        self.transformer.manage_transform(out_bundle,"testfiles/nexus-multi-image.nx","nexus",
                                          self.cf_filename,"cif")
        self.check_vals("incident wavelength",[0.711955],'Real',0.001)

    def testAxisTransform(self):
        """Test that axes are transformed correctly"""
        out_bundle = ["axis id","axis vector","axis offset"]
        self.transformer.manage_transform(out_bundle,"testfiles/adsc_jrh_testfile.nx","nexus",
                           "axis_test.cif","cif")
        # create simple array
        self.cfa.open_file("axis_test.cif")
        self.cfa.open_data_unit()
        new_ids = self.cfa.get_by_name("axis id","Text")
        new_vecs = self.cfa.get_by_name("axis vector","Real")
        new_offsets = self.cfa.get_by_name("axis offset","Real")
        check1 = dict(zip(new_ids,new_vecs))
        check2 = dict(zip(new_ids,new_offsets))
        print 'Test: check1 is ' + `check1`
        print 'Test: check2 is ' + `check2`
        self.failUnless((check1['ELEMENT_Y']==[0,1,0]).all())
        self.failUnless((abs(check2['ELEMENT_X']-[-105.108,107.865,0])<0.001).all())

class GITransformToNXImageTestCase(unittest.TestCase):
    """Check transforms that involve images """
    def setUp(self):
        self.nxa = n.NXAdapter(n.canonical_groupings)
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.transformer = t.TransformManager()
        self.transformer.register(self.nxa,"nexus")
        self.transformer.register(self.cfa,"cif")
        self.transformer.set_dictionary("full_demo_1.0.dic")
        self.nx_filename = 'nx_test_case.h5'
        try:
            os.remove(self.nx_filename)
        except OSError:
            pass

    def check_vals(self,name,value,value_type,tolerance):
        """Check that the given canonical name has the
        stated value"""
        self.nxa.open_file(self.nx_filename)
        self.nxa.open_data_unit()
        new_val = self.nxa.get_by_name(name,value_type)
        if value_type == "Real":
            self.failUnless((abs(new_val-value)<tolerance).all())
        else:
            self.failUnless((new_val == value).all())

    def dumpfile(self,filename):
        """Dump a file for debugging"""
        self.nxa.open_file(filename)
        print self.nxa.filehandle.tree

    def testImageTransform(self):
        """Test that an image is stacked and stored"""
        out_bundle = ["simple scan frame scan id",
                          "simple scan frame frame id",
                          "simple scan data"]
        self.transformer.manage_transform(out_bundle,"testfiles/multi-image-test.cif","cif",
                                          self.nx_filename,"nexus")
        self.nxa.open_file(self.nx_filename)
        self.nxa.open_data_unit()
        dd = numpy.array(self.nxa.get_by_name("simple scan data","Real"))
        # Must always return a list, even for single values
        print 'Image shape is ' + `dd.shape`
        self.failUnless(dd.shape == (5,200,300))

    def testImageAxes(self):
        """Test that the axes are added to an image with precedence"""
        out_bundle = ["simple scan frame scan id","simple scan data",
                          "simple scan frame frame id","data axis id",
                          "data axis precedence"]
        self.transformer.manage_transform(out_bundle,"testfiles/multi-image-test.cif","cif",
                                          self.nx_filename,"nexus")
        nn = n.NXAdapter(n.canonical_groupings)
        nn.open_file(self.nx_filename)
        nn.open_data_unit()
        axis_ids = nn.get_by_name("data axis id","Text")
        axis_precedences = nn.get_by_name("data axis precedence",'Integer')
        print 'Read axes ' + `axis_ids`
        self.failUnless(set(['ELEMENT_X','ELEMENT_Y','GONIOMETER_PHI'])==set(axis_ids))
        self.failUnless(axis_precedences[list(axis_ids).index('GONIOMETER_PHI')]==3)
        

class GITransformFromNXImageTestCase(unittest.TestCase):
    """Check transforms from NX that involve images in NX format"""
    def setUp(self):
        self.nxa = n.NXAdapter(n.canonical_groupings)
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.transformer = t.TransformManager()
        self.transformer.register(self.nxa,"nexus")
        self.transformer.register(self.cfa,"cif")
        self.transformer.set_dictionary("full_demo_1.0.dic")
        self.cif_filename = 'cif_test_case.cif'
        try:
            os.remove(self.cif_filename)
        except OSError:
            pass
        
    def testImageTransform(self):
        """Test that an image is unstacked and stored"""
        import numpy
        out_bundle = ["2D data","2D data identifier"]
        self.transformer.manage_transform(out_bundle,"testfiles/nexus-multi-image.nx","nexus",
                                          self.cif_filename,"cif")
        self.cfa.open_file(self.cif_filename)
        self.cfa.open_data_unit()
        dd = numpy.array(self.cfa.get_by_name("2D data","Integer"))
        self.failUnless(dd.shape == (5,200,300))

class RoundTripTestCase(unittest.TestCase):
    """Test that full round trip preserves information"""
    def setUp(self):
        self.nxa = n.NXAdapter(n.canonical_groupings)
        self.cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.transformer = t.TransformManager()
        self.transformer.register(self.nxa,"nexus")
        self.transformer.register(self.cfa,"cif")
        self.transformer.set_dictionary("full_demo_1.0.dic")
        self.nexus_file = "round_trip_outbound.nx"
        self.nexus_bundle = ["incident wavelength", "wavelength id", "data axis precedence","data axis id",
                        "simple scan data","simple scan frame frame id","simple detector axis id",
                        "simple detector axis vector mcstas","simple detector axis offset mcstas",
                        "goniometer axis id","goniometer axis vector mcstas",
                        "goniometer axis offset mcstas","frame axis location axis id",
                        "frame axis location angular position","frame axis location frame id",
                        "simple scan frame scan id","frame axis location scan id"]
        self.cif_bundle = ["incident wavelength","wavelength id","axis id",
                      "axis vector","axis offset","frame axis location frame id","2D data",
                      "2D data identifier","2D data structure id","frame axis location axis id",
                      "frame axis location angular position", "frame axis location scan id",
                      "data frame id","data frame binary id","data frame array id",
                      "data frame scan id"]
        self.transformer.manage_transform(self.nexus_bundle,"testfiles/multi-image-test.cif","cif",
                                          self.nexus_file,"nexus")
        # dump the file for interest
        nxa = n.NXAdapter(n.canonical_groupings)
        nxa.open_file(self.nexus_file)
        print nxa.filehandle.tree
        self.transformer.manage_transform(self.cif_bundle,self.nexus_file,"nexus",
                                          "round_trip_return.cif","cif")
        self.new_cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.new_cfa.open_file("round_trip_return.cif")
        self.new_cfa.open_data_unit()
        self.old_cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
        self.old_cfa.open_file("testfiles/multi-image-test.cif")
        self.old_cfa.open_data_unit()
        
    def testWavelength(self):
        """Test that we recover the wavelength"""
        w = self.new_cfa.get_by_name("incident wavelength","Real")
        self.failUnless(abs(w-0.711955)<0.001)

    def testPositions(self):
        """Test that images associated with each position are the same"""
        p = self.new_cfa.get_by_name("frame axis location angular position","Real")
        a = self.new_cfa.get_by_name("frame axis location axis id","Text")
        f = self.new_cfa.get_by_name("frame axis location frame id","Text")
        d = self.new_cfa.get_by_name("2D data","Integer")
        di = self.new_cfa.get_by_name("2D data identifier","Integer")
        frame_id = self.new_cfa.get_by_name("data frame id","Text")
        binary_id = self.new_cfa.get_by_name("data frame binary id","Integer")
        op = self.old_cfa.get_by_name("frame axis location angular position","Real")
        oa = self.old_cfa.get_by_name("frame axis location axis id","Text")
        of = self.old_cfa.get_by_name("frame axis location frame id","Text")
        old_frame_id = self.old_cfa.get_by_name("data frame id","Text")
        old_binary_id = self.old_cfa.get_by_name("data frame binary id","Integer")
        od = self.old_cfa.get_by_name("2D data","Integer")
        odi = self.old_cfa.get_by_name("2D data identifier","Integer")
        frame_ref = zip(frame_id,binary_id)
        old_frame_ref = zip(old_frame_id,old_binary_id)
        check_angles = [x for x in zip(a,f,p) if x[0]=="GONIOMETER_PHI"]
        old_check_angles = [x for x in zip(oa,of,op) if x[0]=="GONIOMETER_PHI"]
        for old_axis,old_frame,old_pos in old_check_angles:
            # check by verifying that the images for each angle are the same
            old_binary = [x[1] for x in old_frame_ref if x[0]==old_frame][0]
            new_frame_id = [x[1] for x in check_angles if x[2]==old_pos][0]
            new_binary = [x[1] for x in frame_ref if x[0]==new_frame_id][0]
            print 'Pos test: old pos %s, frame %s, binary %s:' % (old_pos,old_frame,old_binary)
            print 'Pos test: new pos %s, frame %s, binary %s:' % (old_pos,new_frame_id,new_binary)
            old_image = [x[0] for x in zip(od,odi) if x[1]==old_binary][0]
            new_image = [x[0] for x in zip(d,di) if x[1]==new_binary][0]
            self.failUnless((abs(new_image-old_image)<0.1).all())
    
if __name__=='__main__':
    unittest.main()
    #suite = unittest.TestLoader().loadTestsFromTestCase(NXAdapterWriteReadTestCase)
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(NXAdapterInternalRoutinesTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(GITransformFromNXTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(CifAdapterReadTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(GICifInputTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(GITransformToNXTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(GITransformToNXImageTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(GIFunctionalityTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(GITransformFromNXImageTestCase))
    #suite.addTest(unittest.TestLoader().loadTestsFromTestCase(RoundTripTestCase))
    #unittest.TextTestRunner(verbosity=2).run(suite)
