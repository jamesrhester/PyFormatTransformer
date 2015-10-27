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

We use the nexusformat library for access::
  
    from nexusformat import nexus

Configuration data
==================

The following information details the link between canonical name and
how the values are distributed in the HDF5 hierarchy. In general we
can identify three ways of encoding names: (i) as single HDF5 paths,
ending with a NeXus- defined name/attribute from a NeXus class (ii)
those that are encoded structurally; (iii) those that are encoded
within the values of other names.  For the values that can be easily
obtained by specifying a path, we provide a lookup table;
structurally-encoded values can often be found by using special,
pre-defined names.  For the final type, we provide an additional
function that should be applied to values found using the table.
Note that such functions should not perform mathematical calculations
as this is supposed to happen in the ontology.

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
(as for NXtransformations groups).

Our framework includes the notion of "constant" and "multiple-valued"
datanames.  For maximum flexibility, we encode the restriction that
the 

Some canonical names represent multiple dependencies.  These are
indicated by repeating the items above in a list.  Therefore, the total
structure of an entry in the following table is:

"canonical name": [(class combination 1,name 1, placement 1,[function1]),(class combo 2...)]

::

    canonical_name_locations_mx = {
    "source current": [(("NXsource",),"current","NXinstrument",None)],
    "incident wavelength":[(("NXsample","NXbeam"),"incident_wavelength","NXinstrument",None)],
    "probe":[(("NXsource",),"probe","NXinstrument",convert_probe)],
    "start time": [(("NXentry",),"start_time","to be done",None)],
    "axis vector":[(("NXtransformations",),"*@vector","to be done",None)],
    "axis id":[(("NXtransformations",),"*@nxname","to be done",None)],
    "array axis id":[(("NXdetector","NXdata"),"data@axes","to be done",get_axes)],
    "data":[(("NXdetector","NXdata"),"data","to be done",None)]
    }


Finding IDs
-----------

Unique identifiers for objects can sometimes be implicit, either because
one or more datanames are expected to be unique and act as a proxy, or
because position in an array is sufficient.  This table explains how to
generate those IDs that are not pre-defined. ::

    id_equivalents_mx = {
    "incident wavelength id":"incident_wavelength",
    }
  
  

Obtaining values
================

NeXus defines "classes" which are found in the attributes of
an HDF5 group.::

    def get_by_class(entryhandle,classname):
       """Return all groups in entryhandle with class [[classname]]"""
       classes = [a for a in entryhandle.walk() if getattr(a,"nxclass") == classname]
       return classes

    def is_parent(child,putative_parent):
       """Return true if the child has parent type putative_parent"""
       return getattr(child.nxgroup,"nxclass")== putative_parent
    
We could be asked for a child group, in which case we are supposed
to return a unique identifier for that group, which is the fully
qualified path. Note that the asterisk is intended to capture all
fields used in a NXtransformations class, but our test files seem
to contain non-NXtransformations objects, so we test for attributes
even though that is not really what we should have to do.::
       
    def get_by_name(classlist,name):
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
           simpledata = []
           [[simpledata.append(s) for s in r.walk()] for r in classlist]
           simpledata = [s for s in simpledata if s.nxclass in ["NXfield","NXlink"] and hasattr(s,"depends_on")]
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

    def get_axes(axes_string):
        """Extract the axis names for the array data"""
        indi_axes = axes_string.split(":")
        return indi_axes

    def get_axis_order(axis_name):
        """Return the axis precedence for the array data"""
        return axis_string.split(":").index(axis_name)
    
Checking types
==============

We assume our ontology knows about "Real", "Int" and "Text", and check/transform
accordingly. ::

    def check_type(incoming,target_type):
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

    def get_by_location(datahandle, name,value_type,domain=None):
      """Return values as [[value_type]] for [[name]]"""
      nxlocation = canonical_name_locations_mx.get(name,None)
      if nxlocation is None:
          return None
      for nxclassloc,property,dummy,convert_function in nxlocation:
          upper_classes = list(nxclassloc)
          new_classes = get_by_class(datahandle,upper_classes.pop())
          while len(new_classes)>0 and len(upper_classes)>0:
              target_class = upper_classes.pop()
              all_classes = [a for a in new_classes if is_parent(a,target_class)]
              if len(all_classes)==0:
                  return []   
          #flatten
          new_classes = []
          [new_classes.append(a) for a in all_classes if len(a)>0]
      all_names = get_by_name(new_classes,property)
      if len(all_names)==0:
          return []
      if convert_function is not None:
          all_names = map(convert_function,all_names)
      if len(new_classes)==1:   #only one value
          return check_type(all_names[0],value_type)
      else:   #stuff is spread out
          final_list = []
          [final_list.append(a) for a in all_names]
          return map(check_type,final_list)

Setting values
--------------

In this case we need to create the group, and check that the lengths are
correct if the domain is specified.  We have to recreate the standard
NeXus hierarchy here. ::

    def set_by_location(datahandle,name,value,value_type,domain=None):
      """Set value of name (in form class.name) in datahandle"""
      nxclass,property = name.split(".")



NeXus structure
---------------

This is a minimal list for demonstration purposes.  Each key gives its immediate
parent.  We do not consider the option of using multiple parents here.
      
Example driver
==============
Showing how to use these routines. ::

    def process(entry,canonical_name):
        """For demonstration purposes, print out the value of class,name"""
        nxclass,nxname = canonical_name_locations[canonical_name][0:2]
        print "Values of %s, %s" % (nxclass,nxname)
        all_groups = get_by_class(entry,nxclass)
        print "Found %d groups" % len(all_groups)
        all_names = get_by_name(all_groups,nxname)
        for one_name in all_names:
            print `one_name`

        
    if __name__ == "__main__":
        import sys
        if len(sys.argv) > 2:
            filename = sys.argv[1]
            canonical_name = sys.argv[2]
            file = nexus.NXFile(filename,"r").readfile()
            for entry in file.NXentry:
                process(entry,canonical_name)
