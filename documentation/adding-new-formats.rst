Adding new formats to the system
--------------------------------

A class allowing access to a format (a "format adapter") must provide the
following methods:

get_by_name(self,name,value_type,units=None):

Return the value of canonical name ``name`` as a Python list with
entries corresponding to ``value_type``.  Currently ``value_type`` may
be one of ``Text``, ``Real`` or ``Integer``.  Nested lists of values
of these types are possible.  ``Real`` must be of numpy kind f,i or u.
``Integer`` must be type 'i'or 'u' and ``Text`` must have type "O","S" or "U".
``float`` and ``int`` and ``basestring`` types are also acceptable
for non-numpy objects.

set_by_name(self,name,value,value_type,units=None):

Set the value of canonical name ``name`` to ``value``, which is of type
``value_type`` and expressed in units ``units``.  Value will be provided
as an iterable type (usually list, tuple or numpy.array).

open_file(self.filename):

Open a file with the specified format for reading

open_data_unit(self,entryname=None):

Open a particular section of the file representing a single data unit
for reading, with optional data unit identifier ``entryname``. If a
single file contains only a single data unit, this can be a null
operation.

create_data_unit(self,entryname=None):

Create a new data unit with optional name ``entryname``.

close_data_unit(self):

Finish all output to the current data unit.

output_file(self,filename):

Output a new data file containing all of the data units that were previously
created and closed

get_single_names(self):

Return a list of canonical names which must be single valued in a
single data unit.  This allows the transformation software to split
data from more general formats into separate data units.
