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
    # forward declarations
    convert_probe = None
    get_axes = None
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

Lookup for canonical names
--------------------------

For the canonical name given as a key, provide the class combination,
name and hierarchy given in the value.  The class combination is a
list of classes starting from the least deeply nested; in order to be
considered as part of the dataname, only objects matching the list of
classes is considered. In most cases only a single class will be
needed.  We provide a name (which may be blank) if relevant, and
placement instructions.  Placement describes where in the hierarchy to
place new objects of this type when constructing files.  Placement is
not relevant for meaning but is present purely to capture convention.
The first element of the class combination list should be placed within
the class at the end of the placement list.  To gather attributes, an
at sign should be placed at the end of the name and then the attribute.
An asterisk (*) means that all fields in the group should be considered
(as for NXtransformations groups). An asterisk at the end of a group
means that all groups of this type form the values.

Some canonical names represent multiple dependencies.  These are
indicated by repeating the items above in a list.  Therefore, the total
structure of an entry in the following table is:

"canonical name": [(class combination 1,name 1, placement 1,[function1]),(class combo 2...)]

::

    canonical_name_locations_mx = {
    "source current": [(("NXsource",),"current",["NXinstrument"],None)],
    "incident wavelength":[(("NXmonochromator",),"wavelength",["NXinstrument"],None)],
    "probe":[(("NXsource",),"probe",["NXinstrument"],convert_probe)],
    "start time": [(("NXentry",),"start_time","to be done",None)],
    "axis vector":[(("NXtransformations",),"*@vector","to be done",None)],
    "axis id":[(("NXtransformations",),"*@nxname","to be done",None)],
    "data axis id":[(("NXdetector","NXdata"),"data@axes",["NXinstrument"],get_axes)],
    "data":[(("NXdetector","NXdata"),"data",["NXinstrument"],None)],
    "goniometer axis id":[(("NXsample","NXtransformations"),"*","to be done",None)],
    "detector axis id":[(("NXdetector","NXtransformation*"),"",["NXinstrument"],None)],
    "detector axis vector":[(("NXdetector","NXtransformation*"),"@vector",["NXinstrument"],None)]
    }

The following groups list canonical names that map from the same domain (domain ID given first). ::
    
    canonical_groupings_mx = {'wavelength id':['incident wavelength'],
    'detector axis id':['detector axis vector'],
    }



The Adapter Class
=================

We modularise the NX adapter to allow reuse with different configurations and
to hide the housekeeping information. ::

    class NXAdapter(object):
        def __init__(self,location_config,domain_config):
            self.name_locations = location_config
            self.domain_names = domain_config
            self.filehandle = None
            self.current_entry = None
            self.all_entries = []
            # housekeeping values
            self._missing_ids = {}  #waiting for IDs or attributes to be set
            self._written_list = [] #stuff already output
            self._id_orders = {} #remember the order of keys

Finding IDs
-----------

Unique identifiers for objects can sometimes be implicit, either because
one or more datanames are expected to be unique and act as a proxy, or
because position in an array is sufficient.  This table explains how to
generate those IDs that are not pre-defined. ::

            self.id_equivalents_mx = {
            "wavelength id":"incident_wavelength",
            }
  
Where multiple groups of the same type provide part of the key, we place an
entry into this table. ::

            self.id_is_group = {
            }

IDs that are just other names in the same group are listed here. ::

            self.plain_ids = []

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
           field = fields[0]
           if len(fields) == 2:
               attr = fields[1]
           else:
               attr = ""
           if field != "" and field != "*":
               allnames = [getattr(c,field) for c in classlist if hasattr(c,field)]
               simpledata = [s for s in allnames if s.nxclass in ["NXfield","NXlink"]]
           elif field == "*":
               simpledata = [s.nxname for s in classlist]
           else:
               simpledata = classlist
           if len(simpledata) != 0 and attr == "":
               return simpledata
           elif attr != "":
               simpledata = [getattr(s,attr) for s in simpledata if hasattr(s,attr)]
               return simpledata
           groupdata = [s for s in allnames if s.nxclass not in ["NXfield","NXlink"]]
           return [s.nxpath for s in groupdata]

Conversion functions
====================

These functions extract information that is encoded within values instead of having
a name or group-level address. ::

        def get_axes(self,axes_string):
            """Extract the axis names for the array data"""
            indi_axes = axes_string.split(":")
            return indi_axes

        def get_axis_order(self,axis_name):
            """Return the axis precedence for the array data"""
            return axis_string.split(":").index(axis_name)
    
Checking types
==============

We assume our ontology knows about "Real", "Int" and "Text", and check/transform
accordingly. ::

        def check_type(self,incoming,target_type):
            """Make sure that [[incoming]] has values of type [[target_type]]"""
            try:
                incoming_type = incoming.dtype.kind
                incoming_data = incoming.nxdata
            except AttributeError:  #not a dataset, must be an attribute
                incoming_data = incoming
                if isinstance(incoming,basestring):
                    incoming_type = 'S'
                if isinstance(incoming,(int)):
                    incoming_type = 'i'
                if isinstance(incoming,(float)):
                    incoming_type = 'f'
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
          for nxclassloc,property,dummy,convert_function in nxlocation:
              upper_classes = list(nxclassloc)
              is_group_name = (upper_classes[-1][-1] == "*")
              if is_group_name:
                  upper_classes[-1] == upper_classes[-1][:-1]
              new_classes = self.get_by_class(upper_classes.pop())
              while len(new_classes)>0 and len(upper_classes)>0:
                  target_class = upper_classes.pop()
                  new_classes = [a for a in new_classes if self.is_parent(a,target_class)]
                  if len(new_classes)==0:
                      return []   
              #flatten
              flat_classes = []
              [flat_classes.append(a) for a in new_classes if len(a)>0]
          if not is_group_name:
              all_names = self.get_by_name(flat_classes,property)
          else:
              all_names = [a.nxname for a in flat_classes]
          if len(all_names)==0:
              return []
          if convert_function is not None:
              all_names = map(convert_function,all_names)
          if len(flat_classes)==1:   #only one value
              return self.check_type(all_names[0],value_type)
          else:   #stuff is spread out
              final_list = []
              [final_list.append(a) for a in all_names]
              return map(self.check_type,final_list)

Setting values
--------------

To provide maximum flexibility, we allow non-ID values to be set before the
actual domain ID.  In more complex situations (e.g. a value spread across
several groups) this may mean that we don't know how to partition the
values that we have been provided, so in this case we do not write the
values yet, but wait until the ID has been provided. ::

        def set_by_location(self,name,value,value_type,domain=None):
          """Set value of canonical [[name]] in datahandle"""
          location_info = self.name_locations[name]
          # is this an ID item?
          if name in self.domain_names.keys():
              self._id_orders[name] = value
              self.write_with_id(name,location_info,value,value_type)
              self._written_list.append(name)
              waiting_values = [(n[0],n[1][1],n[1][2]) for n in self._missing_ids.items() if n[1][0] == name]
              for one_name,one_values,one_type in waiting_values:
                  self.set_by_location(one_name,one_values,one_type)
                  return
          # else get key name corresponding to this name
          needed_id = [k for k in self.domain_names.keys() if name in self.domain_names[k]]
          if len(needed_id)>0: 
              needed_id = needed_id[0]
          else:
              needed_id = None
          if needed_id is None or needed_id in self._written_list or needed_id in self.id_equivalents_mx.keys():
              self.write_with_id(needed_id,location_info,value,value_type)
              self._written_list.append(name)
          else:
              self._missing_ids.update({name:[needed_id,value,value_type]})
              print 'Updated missing ids: ' + `self._missing_ids` + ' waiting on ' + `needed_id`
          return

Writing a simple value
----------------------

This sets a property or attribute value. [[current_loc]] is an NXgroup;
[[name]] is an HDF5 property or attribute (prefixed by @
sign).  ::

        def write_a_value(self,current_loc,name,value):
            """Write a value to the group"""
            # now we've worked our way down to the actual name
            if '@' not in name:
                current_loc[name] = value
            else:
                base,attribute = name.split('@')
                if base != '' and not current_loc.has_key(base):
                    self._missing_ids.update({name:[base,value,value_type]})
                elif base == '':  #group attribute
                    current_loc.attrs[attribute] = value
                else:
                    current_loc[base].attrs[attribute] = value

Writing a multi-group value
---------------------------

Some values are spread across multiple groups of the same class, with the index into the value
then being the group name itself.  A complication here is that the order in which the groups
are returned may not be the order that they were written in, so we need to access the original
order provided in [[id_order]] to set the groups correctly. ::

        def write_multi_group(self,location,name,values,value_type,id_order=[]):
            """Write values into the groups at location. If name is
            empty, new instances of the last group in the location list are created 
            and named according to the provided values. Otherwise, the
            group names in id_order are accessed and the appropriate values set"""
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
                self.write_a_value(found[0],name,new_value)
                
            
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
                     print 'Location: ' + `location`
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
            if needed_id is None or needed_id in self.id_equivalents_mx.keys() or \
                needed_id in self.plain_ids or \
                needed_id in self.domain_names.keys():   #all done already
                for near_classes,myname,top_classes,dummy in location_info:
                    tc = top_classes[:]
                    tc.extend(near_classes)
                    if tc[-1][-1]=="*":
                        tc[-1] = tc[-1][:-1]
                        if needed_id is not None: 
                            id_order = self._id_orders[needed_id]  #must exist
                        else:
                            id_order = []
                        self.write_multi_group(tc,myname,values,value_type,id_order)
                    else:
                        target_group = self._find_group(tc)
                        self.write_a_value(target_group,myname,values)
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
            used."""  
            entries = [e for e in nxhandle.NXentry] 
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

Closing the unit
----------------

Axes cannot be written until we have both the ID and the equipment specified, as
the location depends on the equipment.  We are forced to wait until the end to
sort this out. ::

        def close_data_unit(self):
            """Finish all processing in nxhandle"""
            self.all_entries.append(self.current_entry)
            self.current_entry = None
            return

        def output_file(self,filename):
            """Output a file containing the data units in self.all_entries"""
            new_root = nexus.NXroot()
            for one_entry in range(len(self.all_entries)):
                setattr(new_root,"entry"+`one_entry`,self.all_entries[one_entry])
            new_root.save(filename)
        
      
Example driver
==============
Showing how to use these routines. Not functional at present. ::

    def process(filename,canonical_name):
        """For demonstration purposes, print out the value of class,name"""
        nxadapter = NXAdapter(canonical_name_locations_mx,[])
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
