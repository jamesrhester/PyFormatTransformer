Introduction
============

This is an demonstration NeXus format adapter. Format adapters are
described in the paper by Hester (2016). They set and return data in a
uniform (domain,name) presentation.  All format adapter sets must
choose how values are to be represented. Here we choose Numpy arrays.
This adapter is not intended to be comprehensive, but instead to show
how a full adapter might be written.

Two core routines are required:
1. get_by_name(name,type,units)
Return a numpy array or string corresponding to
all values associated with name, expressed in 'units'. 
2. set_by_name(domain,name,values,type,units)
Set all values for (domain,name)

We use the nexusformat library for access, and fixup the library
to include NXtransformation. ::
  
    from nexusformat import nexus
    import numpy  #common form for data manipulation
    # fixup
    missing = "NXtransformation"
    docstring = "NXtransformation class"
    setattr(nexus,missing,type(missing,(nexus.NXgroup,),{"_class":missing,"__doc__":docstring}))
    

Configuration data
==================

The following groups list canonical names that map from the same
domain (domain ID given first). In reality, it simply defers writing
of anything in the value list until the key items have been set, so we
can also use it to indicate that we have to wait for the data to be
set before the data axes can be set.

One of the main reasons for using a hierarchical data structure is to
economise on repeated names in multiple keys, so, for example, if we
have multiple detectors each with multiple elements, we can save on
repeating the detector id for each of its component elements by
nesting the element ids within a 'detector' group.  Our format adaptor
has to unpack this, so in the following table the key is a tuple where
the order of elements is the order in which the items are nested.
So, for example, (a,b,c) as a key implies that b is a group within a,
and c may be either a dataset name or an ordering.

A further way of economising on data storage is to use arrays, which
encode an implicit key for each member of the array. HDF5 restricts
arrays to leaf nodes, so such an ordering must be the last member of
any key that uses them. ::
    
    canonical_groupings = {('wavelength id',):['incident wavelength'],
    ('detector axis id',):['detector axis vector mcstas','detector axis offset mcstas','detector axis type'],
    ('goniometer axis id',):['goniometer axis vector mcstas','goniometer axis offset mcstas','goniometer axis type'],
    ('full simple data scan id',):['full simple data'],
    ('data axis id',):['data axis precedence'],
    ('axis location scan id', 'axis location axis id', 'axis location frame id'):['frame axis location angular position']
    }


The Adapter Class
=================

We modularise the NX adapter to allow reuse with different configurations and
to hide the housekeeping information. ::

    class NXAdapter(object):
        def __init__(self,domain_config):
            self.domain_names = domain_config
            self.filehandle = None
            self.current_entry = None
            self.all_entries = []
            self.has_data = [] #do we need to link data when writing

Lookup for canonical names
--------------------------

The following information details the link between canonical name and
how the values are distributed in the HDF5 hierarchy.  A value may
be encoded as a group name, as a field value, or as an attribute of
a field or group. Any named group is assumed to correspond to some
key value, on the principle that entries within that group must in
some sense be functions of that group (and any parent groups), and therefore the group
must be part of a (possibly composite) key.  Some groups will be 'dummy' groups
that are purely organisational, occur only once, and can take arbitrary values, such as an
'instrument' group that is always a singleton.

Conversely, a field or attribute cannot be a key in the current
NeXus arrangement, as nothing has been defined - of course, it would
be possible to define an array-valued field the values of which
indexed to values in another array-valued field, but in this
situation the index itself acts as the key and so such an arrangement
is rather pointless.

Given the above discussion, we can describe the location of an item by
defining the keys that it depends on, in the order in which the
corresponding groups appear in the hierarchy, and then by giving
the field/attribute name together with any 'dummy' groups between
the final key and the group that the field appears in.

The following table is used in conjunction with the domain description table to
locate and write items.  The first entry ('class combination') is a list of any 'dummy' groups
that appear between the last key group and the name itself. The next entry
is the field/attribute name; an empty name means that the group name should
be used/set.  An attribute of a named field is provided by appending an '@'
sign and the attribute name.

An asterisk (*) means that the value should be attached to the group
itself (as for NXtransformations groups).  An empty name means that
the values are those of the group name itself.

Following these location descriptions we have two functions that are
applied to values before output, and after input, to allow transformations. If
the function returns None, nothing is output. This is useful in cases where
the value is encoded within another value elsewhere.

The order is therefore:

"canonical name": (class combination,name, placement,read_function,write_function)

::

            self.name_locations = {
            "source current": (["NXinstrument","NXsource"],"current",None,None),
            "incident wavelength":(["NXinstrument","NXmonochromator",],"wavelength",None,None),
            "probe":(["NXinstrument","NXsource"],"probe",self.convert_probe,None),
            "start time": ([],"@start_time","to be done",None),
            "axis vector mcstas":([],"@vector",None,None),
            "axis offset mcstas":([],"@offset",None,None),
            "axis id":(["NXtransformation"],"",None,None),
            "data axis id":(["NXinstrument","NXdetector","NXdata"],"data@axes",self.get_axes,self.set_axes),
            "data axis precedence":(["NXinstrument","NXdetector","NXdata"],"data@axes",self.get_axis_order,self.create_axes,),
            "full simple data":(["NXinstrument","NXdetector","NXdata"],"data",None,None),
            "goniometer axis id":(["NXsample","NXtransformation"],"",None,None),
            "goniometer axis vector mcstas":([],"@vector",None,None),
            "goniometer axis offset mcstas":([],"@offset",None,None),
            "simple scan goniometer axis positions":([],"positions",None,None),
            "simple scan goniometer axis name":([],"",None,None),
            "detector axis id":(["NXinstrument","NXdetector","NXtransformation"],"",None,None),
            "detector axis vector mcstas":([],"@vector",None,None),
            "detector axis offset mcstas":([],"@offset",None,None),
            "scan id":([],"",[],None,None)  #entry name
            }


Implicit IDs
------------

Data that are sequential are sometimes presented in an array. We
can interpret this array as providing an implicit ID for each
element in the array.  When setting, we use the provided values
to order the array elements; when returning, we can return the
array as the value, and a sequential array for the IDs. Note that
these implicit IDs can be used to index several arrays. ::

            self.ordering_ids = [
            "wavelength id",
            "frame id"
            ]
            
Equivalent IDs
--------------

The hierarchical structure allows us to re-use 'locations'. For
example, 'axis' groups may contain information from a number
of different categories that include an axis as a key.  We list all
of these equivalents here, keyed to the main entry in our location
table.  We expand the location and ordering tables to save checking each time. ::

            self.equivalent_ids = {
            "axis id":["axis location axis id"],
            "scan id":["full simple data scan id"],
            "frame id":["axis location frame id"]
            }

            for k,i in self.equivalent_ids.items():
                for one_id in i:
                    if self.name_locations.has_key(k):
                        self.name_locations[one_id] = self.name_locations[k]
                if k in self.ordering_ids:
                    for one_id in i:
                        self.ordering_ids.append(one_id)

            # for ease of use later
            self.keyed_names = set()
            [self.keyed_names.update(n) for n in self.domain_names.values()]
            self.all_keys = set()
            [self.all_keys.update(n) for n in self.domain_names.keys()]
            # clear housekeeping values
            self.new_entry()


Specific writing orders
-----------------------

If we are writing an attribute, we need the thing that it is an attribute of
to be written first.  Each entry in this dict is a canonical name: the value is
a list of canonical names that can only be written after the key name.  We augment
this list with the domain keys as well, but remove any that are auto-generated. ::

            self.write_orders = {'full simple data':['data axis precedence','data axis id'],
                 'simple scan axis positions':['simple scan axis name'],
                 }
            
            
Handling units
--------------

We are passed a units identifier in some standard notation, which may not always match NeXus
notation. We adopt for convenience the DDLm unit notation, and this table contains any
translations that are necessary to change between them.  If a unit is missing from this table,
it is denoted identically in both the DDLm dictionary and NeXus. ::

            self.unit_conversions = {   
                'metres':     'm',  
                'centimetres':'cm',  
                'millimetres':'mm',  
                'nanometres': 'nm',  
                'angstroms':  'A' , 
                'picometres': 'pm',  
                'femtometres':'fm',
                'celsius': 'C',
                'kelvins':'K'
            }


        def new_entry(self):
            """Initialise all values"""
            self._id_orders = {}     #remember the order of keys
            self._stored = {}        #temporary storage of names

Obtaining values
================

NeXus defines "classes" which are found in the attributes of
an HDF5 group. ::

        def get_by_class(self,parent_group,classname):
           """Return all groups in parent_group with class [[classname]]"""
           classes = [a for a in parent_group.walk() if getattr(a,"nxclass") == classname]
           return classes

        def is_parent(self,child,putative_parent):
           """Return true if the child has parent type putative_parent"""
           return getattr(child.nxgroup,"nxclass")== putative_parent

We return both the value and the units. Note that the asterisk denotes a value
attached to the group itself.::
       
        def get_field_value(self,base_group,name):
           """Return value of name in parent_group"""
           if not self.name_locations.has_key(name):
               raise ValueError, 'Do not know how to retrieve %s' % name
           location,property,dummy,convert_func = self.name_locations.get(name)
           parent_group = self._find_group(location,base_group,create=False)
           units = None #default value
           if name == "_parent":    #record the parent
               return parent_group.nxgroup.nxpath,None
           fields = property.split("@")
           prop = fields[0]
           is_attr = (len(fields) == 2)
           is_property_attr = (is_attr and (prop !="" and prop != "*"))
           is_group = (prop == "" or prop == "*")
           if is_attr:
               attr = fields[1]
           if not is_group:
               allvalues = getattr(parent_group,prop)
               try:
                   units = getattr(allvalues,"units")
               except KeyError:
                   pass
               allvalues = numpy.atleast_1d(allvalues)
           else:
               allvalues = parent_group
           if not is_attr:
               if not is_group:
                   return allvalues,units
               else:
                   if prop == "":
                       return allvalues.nxname,None
                   elif prop == "*":
                       return allvalues.nxvalue,None
           else:
               print 'NX: retrieving %s attribute (prop was %s)' % (attr,prop)
               try:
                   allvalues = getattr(allvalues,attr)  #attribute must exist
               except nexus.NeXusError:
                   raise ValueError, 'Cannot read %s in %s' % (attr,allvalues)
               print 'NX: found ' + `allvalues`
               return allvalues,None

Conversion functions
====================

These functions extract and set information that is encoded within values instead of having
a name or group-level address.  They are passed a list, which in this case is a single-
element list as there is only a single array of data. ::

        def get_axes(self,axes_string):
            """Extract the axis names for the array data"""
            indi_axes = axes_string[0].split(":")
            return numpy.array(indi_axes)

        def get_axis_order(self,axes_string):
            """Return the axis precedence for the array data"""
            axes = self.get_axes(axes_string)
            return numpy.arange(1,len(axes)+1)
    

Setting axes
------------

The axes for a datablock are stored as attributes of that block, with the order of appearance
of the axis corresponding to its precedence.  Therefore, we cannot output the axis id until we
have the precedence, so we simply store the IDs.  As writing of precedence must wait until
we have the IDs, we can skip checking that the axis IDs are present. ::

        def set_axes(self,axis_list):
            """Remember the data axis ids"""
            self.data_axis_ids = axis_list
            return None  #do not write this ever
    
        def create_axes(self,axis_order):
            """Create and set the axis specification string"""
            axes_in_order = range(len(axis_order))
            for axis,axis_pos in zip(self.data_axis_ids,axis_order):
                axes_in_order[axis_pos-1] = axis
            axis_string = ""
            for axis in axes_in_order:
                axis_string = axis_string + axis + ":"
            print 'NX: Created axis string ' + `axis_string[:-1]`
            return axis_string[:-1]
    
Managing units
--------------

Units are obviously better managed using a dedicated Python module. For demonstration
purposes we use a simple 'a+b*m' conversion table. ::

        def manage_units(self,values,old_units,new_units):
            """Convert values from old_units to new_units"""
            if new_units is None or old_units is None or old_units==new_units:
                return values
            import math
            # This table has a constant unit as the second entry in the 
            # tuple for each type of dimension to allow interconversion of all units
            # of that dimension.
            convert_table = {# length
                             ("mm","m"):(0,0.001),
                             ("cm","m"):(0,0.01),
                             ("km","m"):(0,1000),
                             ("pm","m"):(0,1e-9),
                             ("A","m"):(0,1e-10),
                             # angle
                             ("radians","degrees"):(0,180/math.pi),
                             # temperature
                             ("K","C"):(-273,1)
                             }
            if (old_units,new_units) in convert_table.keys():
                 add_const,mult_const = convert_table[(old_units,new_units)]
                 return add_const + mult_const*values #assume numpy array
            elif (new_units,old_units) in convert_table.keys():
                 sub_const,div_const = convert_table[(new_units,old_units)]
                 return (values - sub_const)/div_const
             # else could do a two-stage conversion
            else:
                 poss_units = [n[0] for n in convert_table.keys()]
                 print 'NX: possible unit conversions: ' + `poss_units`
                 if old_units in poss_units and new_units in poss_units:
                     common_unit = [n[1] for n in convert_table.keys() if n[0]==old_units][0]
                     step1 = self.manage_units(values,old_units,common_unit)
                     return self.manage_units(step1,common_unit,new_units)
                 else:
                     raise ValueError, 'Unable to convert between units %s and %s' % (old_units,new_units)

Synthesizing IDs
----------------

The position of an item in an array is a simple way to store unique IDs. So to
generate IDs, we simply generate sequential values. ::

        def make_id(self,value_list):
            """Synthesize an ID"""
            return range(1,len(value_list)+1)

Converting fixed lists
----------------------

When values are drawn from a fixed set of strings, we may need to convert between
those strings. This is currently not implemented. ::

        def convert_probe(self,values):
            """Convert the xray/neutron/gamma keywords"""
            return values

Checking types
==============

We assume our ontology knows about "Real", "Int" and "Text", and check/transform
accordingly. Everything should be an array. We use the built-in units conversion
of NeXus to handle unit transformations. ::

        def check_type(self,incoming,target_type):
            """Make sure that [[incoming]] has values of type [[target_type]]"""
            try:
                incoming_type = incoming.dtype.kind
                if hasattr(incoming,'nxdata'):
                    incoming_data = incoming.nxdata
                else:
                    incoming_data = incoming
            except AttributeError:  #not a dataset, must be an attribute
                incoming_data = incoming
                if isinstance(incoming,basestring):
                    incoming_type = 'S'
                elif isinstance(incoming,(int)):
                    incoming_type = 'i'
                elif isinstance(incoming,(float)):
                    incoming_type = 'f'
                else:
                    raise ValueError, 'Unrecognised type for ' + `incoming`
            if target_type == "Real":
                if incoming_type not in 'fiu':
                    raise ValueError, "Real type has actual type %s" % incoming_type
            # for integer data we could round instead...
            elif target_type == "Int": 
                if incoming_type not in 'iu':
                    raise ValueError, "Integer type has actual type %s" % incoming_type
            elif target_type == "Text":
                if incoming_type not in 'OSU':
                    raise ValueError, "Character type has actual type %s" % incoming_type
            return incoming_data
            
The API functions
=================

Data unit specification
-----------------------

The data unit is described by a list of constant-valued names, or alternatively,
a list of multiple-valued names.  We go with constant-valued in this example,
as there are so many multiple-valued names. ::

        def get_single_names(self):
            """Return a list of canonical ids that may only take a single
            value in one data unit"""
            return ["full simple data scan id"]

Obtaining values
----------------

We are provided with a name.  We find its basic form using self.equivalent_ids, and then use
our name_locations table to extract all values.  Our unit conversion operates on abbreviated
symbols, so we obtain an abbreviated form. ::

        def get_by_name(self, name,value_type,units=None):
          """Return values as [[value_type]] for [[name]]"""
          raw_values,old_units = self.internal_get_by_name(name)
          if raw_values is None or raw_values == []:
              return raw_values
          print 'NX: raw value for %s:' % name + `raw_values`
          before_units = numpy.atleast_1d(map(lambda a:self.check_type(a,value_type),raw_values))
          unit_abbrev = self.unit_conversions.get(units,units)
          old_unit_abbrev = self.unit_conversions.get(old_units,old_units)
          proper_units = self.manage_units(before_units,old_unit_abbrev,unit_abbrev)
          return proper_units

We define a version of get_by_name that returns the value in native format. This is useful
for internal use when we simply care about item equality and structure.  self._stored
contains (value,units) pairs. If we are passed a key that has no primary values defined,
we simply return the values that that key takes. A more comprehensive solution would
take into account keys at higher levels; in such cases this routine will fail. Note
that keys without any values are unlikely to be useful: discuss, particularly in the
case that these keys are in the range of a function of other keys. ::
    
        def internal_get_by_name(self,name):
              """Return a value with native format and units"""
              # first check that it hasn't been stored already
              if name in self._stored:
                  return self._stored[name]
              # find by key, if it is there
              is_a_primary = len([k for k in self.domain_names.values() if name in k])>0
              if is_a_primary:
                  key_arrays = self.get_key_arrays(name)
                  print 'NX: all keys and values for %s: ' % name + `key_arrays`
                  self._stored.update(key_arrays)
                  if name in key_arrays:
                      return key_arrays[name]
                  else:
                      print 'NX: tried to find %s, not found' % `name`
                      raise ValueError, 'Primary name not found: %s' % name
              else:   #might be a key
                  poss_names = [k[1] for k in self.domain_names.items() if name in k[0]]
                  if len(poss_names)==0:
                      raise ValueError, 'No primary name found for key name: %s' % name
                  print 'NX: possible names for %s: ' % name + `poss_names`
                  for pn in poss_names[0]:
                      try:
                          result = self.internal_get_by_name(pn)
                      except ValueError:
                          import traceback
                          traceback.print_exc()
                          continue
                      if name in self._stored:
                          return self._stored[name]
              # if we get to here, we have a dangling key: just return it straight
              result, result_classes = zip(*self.get_group_values(name,self.current_entry))
              return result,None
                      
Obtaining values of groups.  We find the common name in [[name_locations]] and then trip
down the class hierarchy, collecting all groups matching the list of groups.  We return
all of the names, together with the group objects. Only the last group should have
multiple values, as otherwise the upper groups would themselves be keys. ::

        def get_group_values(self,name,parent_group=None):
              """Use our lookup table to get the value of group name relative to parent group"""
              # find the name in our equivalents table
              if parent_group is None:
                  upper_group = self.current_entry
              else:
                  upper_group = parent_group
              print 'NX: searching for value of %s in %s' % (name,upper_group)
              nxlocation = self.name_locations.get(name,None)
              if nxlocation is None:
                  print 'NX: warning - no location found for %s in %s' % (name,upper_group)
                  return None
              nxclassloc,property,convert_function,dummy = nxlocation
              # catch the reference to the entry name itself
              if len(nxclassloc) == 0 or property!= "":
                  raise ValueError, 'Group-valued name has no class or else field/attribute name is set:' + `name`
              upper_classes = list(nxclassloc)
              upper_classes.reverse()
              while len(upper_classes)>1:
                  target_class = upper_classes.pop()
                  new_classes = self.get_by_class(upper_group,target_class)
                  if len(new_classes)>1:   #still more to come
                      raise ValueError, 'Multiple groups found of type %s but only one expected: %s' % (target_class,new_classes)
                  upper_group = new_classes[0]
              new_classes = self.get_by_class(new_classes[0],upper_classes[0])
              if len(new_classes)==0:
                  return None   
              all_values = [s.nxname for s in new_classes]
              print 'NX: for %s obtained %s' % (name,`all_values`)
              if convert_function is not None:
                  all_values = convert_function(all_values)  #
                  print 'NX: converted %s using %s to get %s' % (name,`convert_function`,`all_values`)
              return zip(all_values,new_classes)

This routine is the reverse of the get_sub_tree routine. Given a name, we return a bunch
of flat arrays in a dictionary indexed by key name.  Note that we cannot generate the
value of a key unless we know the structure of the indexed item, as we will need to
duplicate key values for each sub-entry. ::

        def get_key_arrays(self,name):
              """Get arrays corresponding to all keys and values used with name"""
              all_keys = [k for k in self.domain_names.keys() if name in self.domain_names[k]]
              if len(all_keys) == 0:  #not a primary name
                  raise ValueError, 'Request for a key name or non-existent name %s' % name
              all_keys = all_keys[0]
              print 'NX: keys for %s: ' % name + `all_keys`
              if len(all_keys)==0:   #no keys required
                  return {name: self.get_field_value(self.current_entry,name)}
              if len(all_keys)==1 and all_keys[0] in self.ordering_ids:
                  main_data = self.get_field_value(self.current_entry,name)
                  return {name: main_data, all_keys[0]:(self.make_id(main_data),None)}
              all_keys = list(all_keys)
              all_keys.append(name)
              key_tree,dummy = self.get_sub_tree(self.current_entry,all_keys)
              if key_tree is None:
                  raise ValueError, 'No tree found for key list ' + `all_keys`
              print 'NX: found key tree ' + `key_tree`
              final_arrays = []
              units_array = []
              [final_arrays.append([]) for k in all_keys]  #to avoid pointing to the same list
              [units_array.append(None) for k in all_keys]
              self.synthesize_values(final_arrays,key_tree,units_array)
              return dict(zip(all_keys,zip(final_arrays,units_array)))

Note that the following routine discards the units attribute. TODO: make sure that
the appropriate units for each name are appropriately registered. We can assume
for the purposes of this demonstration that units only need to be registered once. ::

        def get_sub_tree(self,parent_group,keynames):
              """Get the key tree underneath parent_group"""
              print 'NX: get_sub_tree called with parent %s, keys %s' % (parent_group,keynames)
              sub_dict = {}
              if len(keynames)==1:
                  return self.get_field_value(parent_group,keynames[0])  #value itself
              keys_and_groups = self.get_group_values(keynames[0],parent_group)
              if keys_and_groups is None:
                  return None
              for another_key,another_group in keys_and_groups:
                  new_tree,units = self.get_sub_tree(another_group,keynames[1:])
                  if new_tree is not None:
                      sub_dict[another_key] = (new_tree,units)
              return sub_dict,None

When putting together arrays from a key tree, we assume that each entry in our tree will
have units attached, which we harvest out and assume to be identical. ::

        def synthesize_values(self,key_arrays,key_tree,units_array):
              """Given a key tree, return an array of equal-length values, one for
              each level in key_tree. Key_arrays and units_array
              should have the same length as the depth of key_tree.

              """
              print 'Called with %s, tree %s' % (`key_arrays`,`key_tree`)
              for one_key in key_tree.keys():
                  if isinstance(key_tree[one_key],dict):
                     extra_length = self.synthesize_values(key_arrays[1:],key_tree[one_key],units_array[1:])
                     key_arrays[0].extend([one_key]*extra_length)
                     print 'Extended %s with %s' % (`key_arrays[0]`,`one_key`)
                  else:
                     value,units = key_tree[one_key]
                     extra_length = len(value)
                     key_arrays[1].extend(value)
                     key_arrays[0].extend([one_key]*len(value))
                     units_array[0] = units
              print 'Key arrays now ' + `key_arrays`
              print 'Units array now ' + `units_array`
              return extra_length * len(key_tree)
          
Setting values
--------------

For simplicity, we simply store everything until the end. This is because writing values requires
knowledge of the key values, as values may be partitioned according to key value (most obviously,
if multiple groups of the same class exist, each class name will be a different key value and
the dependent values will be distributed between each class.) ::

        def set_by_name(self,name,value,value_type,units=None):
          """Set value of canonical [[name]] in datahandle"""
          self._stored[name] = (value,value_type,units)

        def partition(self,first_array,second_array):
            """Partition the second array into segments corresponding to identical values of the 
            first array, returning the partitioned array and the unique values."""
            print 'Partition called with 1st, 2nd:' + `first_array` + ' ' + `second_array`
            combined = zip(first_array,second_array)
            unique_vals = list(set(first_array))
            final_vals = []
            for v in unique_vals:
                final_vals.append([k[1] for k in combined if k[0] == v])
            return final_vals,unique_vals

The following recursive routine creates a tree from equal length arrays.  The output tree, in
the form of a python dictionary, has unique nodes at each level corresponding to the unique
values found in each supplied array.  To allow for bottom-level arrays with more than
one dimension, max_depth can be supplied to terminate earlier.::
                                                                                        
        def create_tree(self,start_arrays,current_depth=0, max_depth=None):
            """Return a tree created by partitioning each array into unique elements, with
            each subsequent array being the next level in the tree. When the final arrays
            have end_length elements the partitioning stops."""
            print 'Creating a tree to depth %s from %s' % (`max_depth`,`start_arrays`)
            if current_depth == max_depth or \
               max_depth is None and len(start_arrays)==1:   #termination criterion
                   return start_arrays[0]
            partitioned = [self.partition(start_arrays[0],a) for a in start_arrays[1:]]
            part_arrays = zip(*[a[0] for a in partitioned])
            sub_tree = dict(zip(partitioned[0][1],[self.create_tree(p,current_depth+1,max_depth) for p in part_arrays]))
            print 'NX: returned ' + `sub_tree`
            return sub_tree
        
        def create_index(self,first_array,second_array):
            """Return second array in a canonical order with ordering given by values in first array.
            The sort order is also returned for reference."""
            sort_order = first_array[:]
            sort_order.sort()
            sort_order = [first_array.index(k) for k in sort_order]
            canonical_order = [second_array[p] for p in sort_order]
            return canonical_order,sort_order

Writing a tree of values
------------------------

This routine writes out a tree of values. ::

        def output_tree(self,parent_group,names,value_tree,ordering_tree):
            """Output a tree of values, with each level corresponding to values in [names]"""
            sort_order = None
            print 'Outputting tree: ' + `value_tree`
            if len(names)==0:  #finished
                return
            if isinstance(value_tree,dict):
                for one_key in value_tree.keys():
                    child_group = self.store_a_group(parent_group,names[0],one_key,self._stored[names[0]][1],self._stored[names[0]][2])
                    self.output_tree(child_group,names[1:],value_tree[one_key],ordering_tree[one_key])
            else:   #we are at the bottom level
                # shortcut for single values
                if ordering_tree != value_tree and (isinstance(value_tree,list) and len(value_tree)>1):
                    print 'Found ordering tree: %s for %s' % (`ordering_tree`,`value_tree`)
                    output_order,sort_order = self.create_index(ordering_tree,value_tree)
                else:
                    output_order = value_tree
                self.store_a_value(parent_group,names[0],output_order,self._stored[names[0]][1],self._stored[names[0]][2])

When storing a value we are provided with a parent group.  We use the name to look up how to
attach the group to the parent group (there may be some intermediate groups). If the group
already exists with the appropriate name, we simply return it,
otherwise we create and return it. We need to handle writing/navigating several group
steps if we have some dummy groups in the way (e.g. NXinstrument). The key philosophy here is
that any groups that appear multiple times must represent a
key of some sort, and therefore will be handled at some stage
when writing non-key values. ::

        def store_a_group(self,parent_group,name,value,value_type,units):
            location_info = self.name_locations[name][0]
            print 'NX: setting %s (location %s) to %s' % (name,`location_info`,value)
            current_loc = parent_group
            if len(location_info)>1:   #some singleton dummy groups above us
                current_loc = self._find_group(location_info[:-1],parent_group)
            target_class = location_info[-1]
            target_groups = [g for g in current_loc.walk() if g.nxclass == target_class]
            found = [g for g in target_groups if g.nxname == value]
            if len(found)>1:
                raise ValueError, 'More than one group with name %s' % value
            elif len(found)==1:
                # already there
                return found[0]
            # not found, we create
            new_group = getattr(nexus,target_class)()
            current_loc[value]= new_group
            print 'NX: created a new %s group value %s' % (target_class,value)
            return new_group

Writing a simple value
----------------------

Simple values are defined with locations relative to the lowermost key used to
index that value. In the case of single values, or
values that take only an index-type key, this means
that the location is relative to the NXentry and the location will therefore be
the whole hierarchy down to the value (and as a corollary, this hierarchy
cannot contain any keyed groups). ::
                                                                
                              
        def store_a_value(self,parent_group,name,value,value_type,units):
            """Store a non-group value (attribute or field)"""
            location_info = self.name_locations[name]
            group_location = location_info[0]
            print 'NX: setting %s (location %s) to %s' % (name,`location_info`,value)
            current_loc = self._find_group(group_location,parent_group)
            self.write_a_value(current_loc,location_info[1],value,value_type,units)
                              
Writing a simple value
----------------------

This sets a property or attribute value. [[current_loc]] is an NXgroup;
[[name]] is an HDF5 property or attribute (prefixed by @
sign).  ::

        def write_a_value(self,current_loc,name,value,value_type,unit_abbrev):
            """Write a value to the group"""
            # now we've worked our way down to the actual name
            if '@' not in name:
                current_loc[name] = value
                if unit_abbrev is not None:
                    current_loc[name].units = unit_abbrev
            else:
                if unit_abbrev is not None:
                    print 'Warning: trying to set units on attribute'
                base,attribute = name.split('@')
                if base != '' and not current_loc.has_key(base):
                    raise AttributeError,'NX: Cannot write attribute %s as field %s missing' % (attribute,base)
                elif base == '':  #group attribute
                    current_loc.attrs[attribute] = value
                else:
                    current_loc[base].attrs[attribute] = value
                            
Utility routine to select/create a group
----------------------------------------

::

        def _find_group(self,location,start_group,create=True):
            """Find or create a group corresponding to location and return the NXgroup"""
            current_loc = start_group
            if len(location)==0:
                return start_group
            for nxtype in location:
                candidates = [a for a in current_loc.walk() if getattr(a,"nxclass") == nxtype]
                if len(candidates)> 1:
                     raise ValueError, 'Non-singleton group %s in item location: ' % nxtype + `location`
                if len(candidates)==1:
                     current_loc = candidates[0]
                elif create:
                     new_group = getattr(nexus,nxtype)()
                     current_loc[nxtype[2:]]= new_group
                     print 'NX: created new group %s of type %s' % (nxtype[2:],nxtype)
                     current_loc = new_group
            return current_loc

            
Writing a named group
---------------------

Sometimes we want to give a group a specific name.  This is the routine for that. ::

        def write_a_group(self,name,location,nxtype):
            """Write a group of nxtype in location"""
            current_loc = self._find_group(location)
            current_loc.insert(getattr(nexus,nxtype)(),name=name)


Dataname-specific routines
--------------------------

Housekeeping
------------

We provide routines for opening and closing a file and a data unit. ::

        def open_file(self,filename):
            """Open the NeXus file [[filename]]"""
            self.filehandle = nexus.nxload(filename,"r")

        def open_data_unit(self, entryname=None): 
            """Open a
            particular entry .If
            entryname is not provided, the first entry found is
            used and a unique name created"""  
            entries = [e for e in self.filehandle.NXentry] 
            if entryname is None: 
                self.current_entry = entries[0]
            else: 
                our_entry = [e for e in entries if e.nxname == entryname]
                if len(our_entry) == 1:
                    self.current_entry = our_entry[0]
                else:
                    raise ValueError, 'Entry %s not found' % entryname

        def create_data_unit(self,entryname = None):
            """Start a new data unit"""
            self.current_entry = nexus.NXentry()
            self.current_entry.nxname = 'entry' + `len(self.all_entries)+1`

Closing the unit
----------------

We create a missing_ids list containing a list of [old_name, wait_name] where old_name is waiting
for wait_name.  We  throw an error as soon as we
cannot find the values in self._stored.  In order to output values that were provided to us as
flat arrays, we have to partition those flat arrays into groups according to the key structure.
Those values that do not require this are stored in [[straight_names]].  For the other values,
we read off the key sequence, and create a tree of key values which we then write out.
Note that if the final key is an ordering key, we need to create a separate tree for it so
that we can order the values in each branch of the tree correctly. ::

        def close_data_unit(self):
            """Finish all processing"""
            # check our write order list
            output_names = set(self._stored.keys())
            self.has_data.append('full simple data' in output_names)
            print 'NX:now outputting ' + `output_names`
            for name in output_names:
                wait_names = set([k for k in self.write_orders.keys() if name in self.write_orders[k]])
                # check our id dependencies
                [wait_names.update(list(k)) for k in self.domain_names.keys() if name in self.domain_names[k]]
                print 'Wait names now: ' + `wait_names`
                waiting = wait_names.difference(output_names)
                if len(waiting)>0:
                    raise ValueError, "Following IDs not found but needed in order to output %s:" % name + `waiting`
            # now write out all names
            # get all key-dependent names
            primary_names = set()
            [primary_names.update(n[1]) for n in self.domain_names.items()\
             if len(n[0])>1 or n[0][0] not in self.ordering_ids]
            # remove those that only require ordering keys
            primary_names = primary_names.intersection(output_names)
            # primary names require keys
            print 'NX: now outputting primary names ' + `primary_names`
            for pn in primary_names:
                pn_keys = [k for k in self.domain_names.keys() if pn in self.domain_names[k]]
                pn_value = self._stored[pn][0]
                if len(pn_keys)>0:
                    pn_keys = pn_keys[0]
                # pick up ordering keys
                ordering_keys = [k for k in pn_keys if k in self.ordering_ids]
                # check that there is one, at the end only
                if len(ordering_keys)>1:
                    raise ValueError, 'Only one ordering key possible for %s, but found %s' % (pn,`ordering_keys`)
                ordering_key = None
                if len(ordering_keys)==1:
                    ordering_key = ordering_keys[0]
                    if pn_keys.index(ordering_key)!=len(pn_keys)-1:
                        raise ValueError, 'Only the final key can be an ordering key: %s in %s for name %s' % (ordering_key,`pn_keys`,pn)
                    pn_keys = pn_keys[:-1]
                pn_key_vals = [self._stored[k][0] for k in pn_keys]+[pn_value]
                tree_for_output = self.create_tree(pn_key_vals,max_depth=len(pn_keys))
                tree_for_ordering = tree_for_output
                if ordering_key is not None:   #need to sort
                    pn_key_vals[-1] = self._stored[ordering_key][0]
                    tree_for_ordering = self.create_tree(pn_key_vals,max_depth=len(pn_keys))
                # now we need to output by traversing our output tree
                self.output_tree(self.current_entry,pn_keys+(pn,),tree_for_output,tree_for_ordering)
                # remove names from list
                output_names.remove(pn)
                output_names.difference_update(pn_keys)
                output_names.discard(ordering_key)
            # up next: names that are non-ordering keys, with no primary item
            dangling_keys = self.all_keys.intersection(output_names).difference(self.ordering_ids)
            print 'NX: found dangling keys %s' % `dangling_keys`
            while len(dangling_keys)>0:
                dk = dangling_keys.pop()
                key_seq = [list(k) for k in self.domain_names.keys() if dk in k][0]
                key_seq = [k for k in key_seq[:key_seq.index(dk)+1] if k in self._stored.keys()]
                key_vals = [self._stored[k][0] for k in key_seq]
                key_vals.append([[]]*len(key_vals[-1]))  #dummy value
                tree_for_output = self.create_tree(key_vals,max_depth=len(key_vals)-1)
                self.output_tree(self.current_entry,key_seq,tree_for_output,tree_for_output)
                output_names.difference_update(key_seq)
                dangling_keys.difference_update(key_seq)
            # straight names require no keys, or ordering keys only
            straight_names = output_names.difference(self.ordering_ids)
            print 'NX: now outputting straight names ' + `straight_names`
            for sn in straight_names:
                if sn not in self.keyed_names:
                    output_order = self._stored[sn][0]
                else:   #has an ordered key only
                    ordered_key = [k[0] for k in self.domain_names.keys() if sn in self.domain_names[k]][0]
                    output_order,sort_order = self.create_index(self._stored[ordered_key][0],
                                                                self._stored[sn][0])
                    output_names.remove(ordered_key)
                self.store_a_value(self.current_entry,sn,output_order,self._stored[sn][1],
                                       self._stored[sn][2])
                output_names.remove(sn)
            # Finished: check that nothing is left
            if len(output_names)>0:
                raise ValueError, 'Did not output all data: %s remain' % `output_names`
            self.all_entries.append(self.current_entry)
            self.current_entry = None
            self.new_entry()
            return

        def output_file(self,filename):
            """Output a file containing the data units in self.all_entries"""
            root = nexus.NXroot()
            for one_entry,link_data in zip(self.all_entries,self.has_data):
                root.insert(one_entry)
                if link_data:
                    main_data = one_entry.NXinstrument[0].NXdetector[0].data
                    print 'Found main data at' + `main_data`
                    data_link = nexus.NXdata()
                    one_entry.data = data_link
                    data_link.makelink(main_data)
                    one_entry.data.nxsignal = one_entry.data.data
            root.save(filename)
      
Example driver
==============
Showing how to use these routines. Not functional at present. ::

    def process(filename,canonical_name):
        """For demonstration purposes, print out the value of class,name"""
        nxadapter = NXAdapter([])
        nxadapter.open_file(filename)
        nxadapter.open_data_unit()
        wave_val = nxadapter.get_by_name(canonical_name,'Real')
        print `wave_val`

    if __name__ == "__main__":
        import sys
        if len(sys.argv) > 2:
            filename = sys.argv[1]
            canonical_name = sys.argv[2]
            process(filename,canonical_name)
