Introduction
============

This is an demonstration NeXus format adapter. Format adapters are
described in the paper by Hester (2016). They set and return data in a
uniform (domain,name) presentation.  All format adapter sets must
choose how values and units are to be presented. Here we choose Numpy
representation, and standard units of 'metres' for length.  This
adapter is not intended to be comprehensive, but instead to show how a
full adapter might be written.

Three routines are required:
1. get_by_location(name,type,domain=None)
Return a numpy array or string corresponding to
all values associated with name. Type
is restricted to "real", "text" or "int".
2. set_by_location(domain,name,values,type)
Set all values for (domain,name)
3. set_by_domain_value(domain,domain_value,name,value,type)
Set the value of name corresponding to the value of domain equalling (domain,name)

We use the nexusformat library for access, and fixup the library
to include NXtranformation. ::
  
    from nexusformat import nexus
    import numpy  #common form for data manipulation
    # fixup
    missing = "NXtransformation"
    docstring = "NXtransformation class"
    setattr(nexus,missing,type(missing,(nexus.NXgroup,),{"_class":missing,"__doc__":docstring}))
    

Configuration data
==================

The following information details the link between canonical name and
how the values are distributed in the HDF5 hierarchy. In general we
can identify four ways of encoding values corresponding to a single
name: (i) as unique HDF5 paths, ending with a NeXus- defined
property/attribute from a NeXus class (ii) those that are encoded
structurally (e.g. in the order or as parents); (iii) multiple values
of a single NeXus property arising from multiple classes; (iv) those
that are encoded within the value of a name.  For the values that can
be easily obtained by specifying a path, we provide a lookup table;
structurally-encoded values can often be found by using special,
pre-defined names.  For the final type, we provide an additional
function that should be applied to values found using the table.  Note
that such functions should not perform mathematical calculations as
this is supposed to happen in the ontology.

Furthermore, the adapter needs to know where the domain IDs are
located in order to properly distribute and write values when
creating a file.  This is provided during initialisation.


The following groups list canonical names that map from the same domain (domain ID given first). In reality,
it simply defers writing of anything in the value list until the key item has been set, so we can also
use it to indicate that we have to wait for the data to be set before the data axes can be set. ::
    
    canonical_groupings = {'wavelength id':['incident wavelength'],
    'detector axis id':['detector axis vector','detector axis offset','detector axis type'],
    'full simple data scan id':['full simple data'],
    'data axis id':['data axis precedence']
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

Finding IDs
-----------

Sometimes an ID is implicit, because there is only one of
something, for example, a single scan.  This list gives
IDs that are auto-generated and therefore do not have to
be set separately. They are automatically considered to
be present when writing out, but can be additionally
"set" (which may or may not do anything). ::

            self.id_equivalents = [
            "wavelength id",   #in NeXus appears implicit
            "full simple data scan id" #singleton ID
            ]

            # clear housekeeping values
            self.new_entry()


Specific writing orders
-----------------------

If we are writing an attribute, we need the thing that it is an attribute of
to be written first.  Each entry in this dict is a canonical name: the value is
a list of canonical names that can only be written after the key name.  We augment
this list with the domain keys as well, but remove any that are auto-generated. ::

            self.write_orders = {'full simple data':['data axis precedence','data axis id'],}
            self.write_orders.update(self.domain_names)
            for idname in self.id_equivalents:
                if self.write_orders.has_key(idname):
                    del self.write_orders[idname]

Lookup for canonical names
--------------------------

We endeavour to provide a uniform way of describing how values are
located and set.  In order to do this we provide,
for the canonical name given as a key, the class combination,
name and hierarchical location.  The class combination is a
list of classes starting from the least deeply nested; in order to be
considered as part of the dataname, only objects matching the list of
classes is considered. In most cases only a single class will be
needed.  We provide a name (which may be blank) if relevant, and
placement instructions.  Placement describes where in the hierarchy to
place new objects of this type when constructing files.  Placement is
not relevant for meaning but is present purely to capture convention.
The first element of the class combination list should be placed within
the class at the end of the placement list.  To gather attributes, an
at sign should be placed after the name, followed by the attribute.
An asterisk (*) means that all fields in the group should be considered
(as for NXtransformations groups).  An empty name means that the values
are those of the group name itself.  

Following these location descriptions we have two functions that are
applied to values before output, and after input, to allow transformations. If
the function returns None, nothing is output. This is useful in cases where
the value is encoded within another value elsewhere.

The order is therefore:

"canonical name": (class combination,name, placement,read_function,write_function)

::

            self.name_locations = {
            "source current": (["NXsource"],"current",["NXinstrument"],None,None),
            "incident wavelength":(["NXmonochromator",],"wavelength",["NXinstrument"],None,None),
            "wavelength id":(["NXmonochromator"],"wavelength",["NXinstrument"],self.make_id,None),
            "probe":(["NXsource"],"probe",["NXinstrument"],self.convert_probe,None),
            "start time": ([],"@start_time","to be done",None),
            "axis vector":(["NXtransformation"],"@vector",[],None,None),
            "axis id":(["NXtransformation"],"",[],None,None),
            "data axis id":(["NXdetector","NXdata"],"data@axes",["NXinstrument"],self.get_axes,self.set_axes),
            "data axis precedence":(["NXdetector","NXdata"],"data@axes",["NXinstrument"],self.get_axis_order,self.create_axes,),
            "full simple data":(["NXdetector","NXdata"],"data",["NXinstrument"],None,None),
            "goniometer axis id":(["NXsample","NXtransformation"],"",[],None,None),
            "detector axis id":(["NXdetector","NXtransformation"],"",["NXinstrument"],None,None),
            "detector axis vector":(["NXdetector","NXtransformation"],"@vector",["NXinstrument"],None,None),
            "detector axis offset":(["NXdetector","NXtransformation"],"@offset",["NXinstrument"],None,None),
            "full simple data scan id":([],"",[],None,None)  #entry name
            }

        def new_entry(self):
            """Initialise all values"""
            self._missing_ids = {}   #waiting for IDs or attributes to be set
            self._written_list = []  #stuff already output
            self._id_orders = {}     #remember the order of keys
            self._stored = {}        #temporary storage of names


Obtaining values
================

NeXus defines "classes" which are found in the attributes of
an HDF5 group.::

        def get_by_class(self,classname):
           """Return all groups in entryhandle with class [[classname]]"""
           classes = [a for a in self.current_entry.walk() if getattr(a,"nxclass") == classname]
           return classes

        def is_parent(self,child,putative_parent):
           """Return true if the child has parent type putative_parent"""
           return getattr(child.nxgroup,"nxclass")== putative_parent

We could be asked for a child group, in which case we are supposed
to return a unique identifier for that group, which is the fully
qualified path. Note that the asterisk is intended to capture the names
of all the groups provided::
       
        def get_by_name(self,classlist,name):
           """Return all values of name for objects in classlist"""
           if name == "_parent":    #record the parent
               return [s.nxgroup.nxpath for s in classlist]
           fields = name.split("@")
           prop = fields[0]
           is_attr = (len(fields) == 2)
           is_property_attr = (is_attr and prop !="")
           is_group = (prop == "")
           if is_attr:
               attr = fields[1]
           if not is_group:
               allvalues = [getattr(c,prop) for c in classlist]
           else:
               allvalues = classlist
           if not is_attr:
               if not is_group:
                   return allvalues
               else:
                   return [s.nxname for s in allvalues]
           else:
               print 'NX: retrieving %s attribute (prop was %s)' % (attr,prop)
               allvalues = [getattr(s,attr) for s in allvalues]  #attribute must exist
               print 'NX: found ' + `allvalues`
               return allvalues

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

Synthesizing IDs
----------------

Some ID values are implicit, e.g. the wavelength can be identified only by
the number itself or the position in the list.  When asked for an ID we
return the order in the list.  This only works because nothing else
in the file refers to the wavelength. ::

        def make_id(self,value_list):
            """Synthesize an ID"""
            return range(len(value_list))

Converting fixed lists
----------------------

When values are drawn from a fixed set of strings, we may need to convert between
those strings. ::

        def convert_probe(self,values):
            """Convert the xray/neutron/gamma keywords"""
            return values

Checking types
==============

We assume our ontology knows about "Real", "Int" and "Text", and check/transform
accordingly. Everything should be an array. ::

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

We are provided with a name, and possibly a domain.  The name is of the form
"class.property", where the property portion could refer to either a property
or an attribute.::

        def get_by_location(self, name,value_type,domain=None):
          """Return values as [[value_type]] for [[name]]"""
          nxlocation = self.name_locations.get(name,None)
          if nxlocation is None:
              return None
          nxclassloc,property,dummy,convert_function,dummy = nxlocation
          upper_classes = list(nxclassloc)
          new_classes = self.get_by_class(upper_classes.pop())
          while len(new_classes)>0 and len(upper_classes)>0:
              target_class = upper_classes.pop()
              new_classes = [a for a in new_classes if self.is_parent(a,target_class)]
              if len(new_classes)==0:
                  return []   
          all_values = self.get_by_name(new_classes,property)
          print 'NX: for %s obtained %s ' % (name,`all_values`)
          if convert_function is not None:
              all_values = convert_function(all_values)  #
              print 'NX: converted %s using %s to get %s' % (name,`convert_function`,`all_values`)
          return numpy.atleast_1d(map(lambda a:self.check_type(a,value_type),all_values))

Setting values
--------------

We first check that this value is not waiting on any unwritten values.  If so, we simply
add this value to our waiting list.  If we can write the value, we find its corresponding
ID and write the value (the ID is necessary to get the order right), then we check to see 
if we have now made other values writeable and call ourselves recursively.  ::

        def set_by_location(self,name,value,value_type,domain=None):
          """Set value of canonical [[name]] in datahandle"""
          # drop any synthesized IDs on the floor
          if name in self.id_equivalents:
              return   #done
          # check our write order list
          wait_names = set([k for k in self.write_orders.keys() if name in self.write_orders[k]])
          waiting = wait_names.difference(self._written_list)
          if len(waiting)>0:
              self._missing_ids[name] = self._missing_ids.get(name,set()) | waiting
              print 'Updated missing ids: ' + `self._missing_ids` + ' waiting on ' + `waiting`
              self._stored[name] = (value,value_type)
          else:
              # we can write this
              self.store_a_value(name,value,value_type)

        def store_a_value(self,name,value,value_type):
            """This is called when we can directly output a name"""
            location_info = self.name_locations[name]
            print 'NX: setting %s (location %s) to %s' % (name,`location_info`,value)
            if name in self.domain_names.keys():
                print 'NX: setting key value %s' % `name`
                self._id_orders[name] = value
                self.write_with_id(name,location_info,value,value_type)
                self._written_list.append(name)
            else:
              # else get key name corresponding to this name
              needed_id = [k for k in self.domain_names.keys() if name in self.domain_names[k]]
              if len(needed_id)>0: 
                  needed_id = needed_id[0]
              else:
                  needed_id = None
              if needed_id is None or needed_id in self._written_list or needed_id in self.id_equivalents:
                  self.write_with_id(needed_id,location_info,value,value_type)
                  self._written_list.append(name)
              else:
                  print 'NX: about to abort, missing list is ' + `self._missing_ids`
                  raise ValueError, '%s missing for writing %s but %s is not in missing list: ' % (needed_id,name,needed_id)


Writing a simple value
----------------------

This sets a property or attribute value. [[current_loc]] is an NXgroup;
[[name]] is an HDF5 property or attribute (prefixed by @
sign).  ::

        def write_a_value(self,current_loc,name,value,value_type):
            """Write a value to the group"""
            # now we've worked our way down to the actual name
            if '@' not in name:
                current_loc[name] = value
            else:
                base,attribute = name.split('@')
                if base != '' and not current_loc.has_key(base):
                    print 'Not writing attribute %s as field %s missing; assume this is\
                    scheduled in self._missing_ids' % (attribute,base)
                    pass
                elif base == '':  #group attribute
                    current_loc.attrs[attribute] = value
                else:
                    current_loc[base].attrs[attribute] = value

Writing a multi-group value
---------------------------

Some values are spread across multiple groups of the same class, with the index into the value
then being the group name itself.  A complication here is that the order in which the groups
are returned may not be the order that they were written in, so we need to access the original
order provided in [[id_order]] to set the groups correctly.  A special case is the name of
the top-level group. If location is the empty list, we store the length-one value that is
provided for when we output the entry. ::

        def write_multi_group(self,location,name,values,value_type,id_order=[]):
            """Write values into the groups at location. If name is
            empty, new instances of the last group in the location list are created 
            and named according to the provided values. Otherwise, the
            group names in id_order are accessed and the appropriate values set"""
            if len(location)==0:
               print "NX: Setting entry name : given " + `values`
               if len(values)!= 1:
                   raise ValueError, "More than one value provided for entry: cannot write multiple entries %s" % `values`
               self.current_entry.nxname = values[0]
               return
            current_loc = self._find_group(location[:-1])
            if name == "":
                for gname in values:
                    new_group = getattr(nexus,location[-1])()
                    current_loc[gname]= new_group
                return
            #print `[("%s(%s) " % (g.nxname,g.nxclass)) for g in current_loc.walk()]`
            target_groups = [g for g in current_loc.walk() if g.nxclass == location[-1]]
            #print `["%s " % g.nxname for g in target_groups]`
            for id_name,new_value in zip(id_order,values):
                found = [g for g in target_groups if g.nxname == id_name]
                if len(found)>1 or len(found)==0:
                    raise ValueError, 'Cannot find group with name %s' % id_name
                self.write_a_value(found[0],name,new_value,value_type)
                
            
Utility routine to select/create a group
----------------------------------------

::

        def _find_group(self,location):
            """Find or create a group corresponding to location and return the NXgroup"""
            current_loc = self.current_entry
            for nxtype in location:
                candidates = [a for a in current_loc.walk() if getattr(a,"nxclass") == nxtype]
                if len(candidates)> 1:
                     raise ValueError, 'Not implemented: multiple classes for single value ' + `location`
                if len(candidates)==1:
                     current_loc = candidates[0]
                else:
                     new_group = getattr(nexus,nxtype)()
                     current_loc[nxtype[2:]]= new_group
                     current_loc = new_group
            return current_loc

            
Writing a named group
---------------------

Sometimes we want to give a group a specific name.  This is the routine for that. ::

        def write_a_group(name,location,nxtype):
            """Write a group of nxtype in location"""
            current_loc = self._find_group(location)
            current_loc.insert(getattr(nexus,nxtype)(),name=name)

            
Writing an ID value
-------------------

When we have an ID stored, we can write out the corresponding values and maintain
the order.  This routine also trivially applies to IDs themselves. ::

        def write_with_id(self,needed_id,location_info,values,value_type):
            """Write a value where the ID is present already"""
            # depends on type of ID
            if needed_id is None or needed_id in self.id_equivalents or \
                needed_id in self.domain_names.keys():   #all done already
                near_classes,myname,top_classes,dummy,set_transform = location_info
                if set_transform is not None:
                    values = set_transform(values)
                    if values is None: return   #nothing to do
                tc = top_classes[:]
                tc.extend(near_classes)
                if myname == "" or myname.split("@")[0]=="":  # a group
                    if needed_id is not None: 
                        id_order = self._id_orders[needed_id]  #must exist
                    else:
                        id_order = []
                    print 'NX: setting %s/%s to %s' % (`tc`,`myname`,`values`)
                    self.write_multi_group(tc,myname,values,value_type,id_order)
                else:
                    target_group = self._find_group(tc)
                    self.write_a_value(target_group,myname,values,value_type)
            else:
                raise ValueError, 'Not yet able to handle non-simple IDs: %s' % needed_id
            
Writing with ID present
-----------------------

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

Our missing_ids list contains a list of [old_name, wait_name] where old_name is waiting
for wait_name.  We resolve all of these at the end, and throw an error as soon as we
cannot find the values in self._stored. ::

        def close_data_unit(self):
            """Finish all processing"""
            print 'NX: Now outputing delayed items: missing list, written list:'
            print `self._missing_ids`
            print `self._written_list`
            # create a list indexed by the item we want to write, listing what it was waiting for
            can_write = [n[0] for n in self._missing_ids.items() if n[1].issubset(self._written_list)]
            while len(can_write)>0:
                print 'NX: can write ' + `can_write`
                for one_name in can_write:
                    one_values,one_type = self._stored[one_name]
                    self.store_a_value(one_name,one_values,one_type)
                    del self._missing_ids[one_name]
                can_write = [n[0] for n in self._missing_ids.items() if n[1].issubset(self._written_list)]
            
            self.all_entries.append(self.current_entry)
            self.current_entry = None
            if len(self._missing_ids)>0:
                raise ValueError, "Invalid data unit written, need " + `self._missing_ids.values()`
            self.new_entry()
            return

        def output_file(self,filename):
            """Output a file containing the data units in self.all_entries"""
            new_root = nexus.NXroot()
            for one_entry in range(len(self.all_entries)):
                new_root.insert(self.all_entries[one_entry])
            new_root.save(filename)
      
Example driver
==============
Showing how to use these routines. Not functional at present. ::

    def process(filename,canonical_name):
        """For demonstration purposes, print out the value of class,name"""
        nxadapter = NXAdapter([])
        nxadapter.open_file(filename)
        nxadapter.open_data_unit()
        wave_val = nxadapter.get_by_location(canonical_name,'Real')
        print `wave_val`

    if __name__ == "__main__":
        import sys
        if len(sys.argv) > 2:
            filename = sys.argv[1]
            canonical_name = sys.argv[2]
            process(filename,canonical_name)
