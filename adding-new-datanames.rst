How to add new datanames to the system
======================================

The following assumes that you have already defined a canonical name
and edited the DDLm dictionary appropriately.  For the purposes of
this example, suppose that the new canonical name is ``frame axis
location angular position``, which is a function of (i.e. depends on)
``frame axis location scan id`` , ``frame axis location axis id`` and
``frame axis location frame id``.

NeXus
=====

NeXus configuration directives are located near the top of the
``nx_format_adapter.py`` file.  Dependencies will become either group nodes,
or else an ordering id that is encoded in the order that value appears.
Therefore, only one ordering id can be specified for each dataname.

Step 1: Add canonical dependencies
----------------------------------

Add a tuple describing the dependencies to the ``canonical_groupings`` global dictionary:
::

    canonical_groupings = ...,
       ('frame axis location scan id','frame axis location axis id', 'frame axis location frame id'):['frame axis location angular position'],
    ....


The order in which the dependencies are specified is important, as the NeXus tree is traversed by
first finding each of the dependencies in order.  In this case, ``scan id`` is found, and then
each ``scan id`` node is traversed down to the ``axis id`` nodes, then the ``frame id`` ordering
id is used to write ``angular position`` in some consistent order, or to create ``frame id``
when reading ``angular position``.

Step 2: Describe NeXus locations
--------------------------------

Add a line to ``self.name_locations`` describing where in a NeXus file
to read/write ID and dataname values.  An object is found in the NeXus file by
first traversing the hierarchy using each of the keys in the key list
in order, and then using the location table to find the dataname.
Each entry in this table has structure ``([class tree],location in
class, read_function, write_function)``.  The class tree is a list of
NeXus classes between the bottom-most class reached by the
dependencies, down to the class containing the dataname.  The dataname
itself gives the location in the class: if it is empty, the name of
the node becomes the value.  An "@" sign is used to indicate an
attribute of the class or a field. In our example we have field name
"position" which is a field of the class specified by the ``axis id``
dependency (``NXtransformation``), so there is no class tree
specified.

Traversal starts from the top of NXentry.  ``scan id`` has no class
list, so following reading/writing of the ``scan id`` to the NXentry
class we are still at the top of the tree. ``axis id`` traverses
to ``NXtransformation`` (skipping any singleton classes on the way,
as these cannot act as keys) when reading, and then finally the ``position``
field of this class is read.  Because NeXus specifications dictate
that ``NXtransformation`` classes are nested inside singleton ``NXsample``
or ``NXinstrument/NXdetector`` classes, when writing we wait until
the ``NXtransformation`` classes have been written before writing
out these items (see below).

::

    "frame axis location axis id":(["NXtransformation"],"",None,None),
    "frame axis location angular position":([],"position",None,None),
    "simple scan frame scan id":([],"",None,None), # top level


Step 3: Identify ordering ids
-----------------------------

If the final dependency in the dependency list is an ordering id, the
other ordering ids that should provide matching values must be
indicated.  The ``self.equivalent_ids`` variable is a dictionary
listing equivalent ids, including for items specified in
``self.ordering_ids``. If an equivalent id is present in ``self.ordering_ids``,
you should add the new ordering id to ``self.equivalent_ids``. This
ensures that the IDs that are generated on read match one another. In
our example, ``frame axis location frame id`` is equivalent to ``frame id``:

::

    "frame id":["frame axis location frame id","simple scan frame frame id"],


Step 4: Write order
-------------------

Items lower down the hierarchy rely on the presence of earlier items
in order to be written.  Often we can create the key items as we go,
but in certain circumstances this is not possible. This can occur
where a given item requires only a single key in order to access it, but
that key is at the end of a multi-class chain.  In our case, ``angular position``
requires only an axis name, but axes are conventionally separated into
NXdetector and NXsample classes.  We therefore wait until these axes have been
written before adding our positions, rather than creating NXtransformation
classes outside NXdetector/NXsample classes.  The class variable ``self.write_orders``
is a dictionary of such dependencies, where the dictionary keys should
be written (if available) before any of the associated dictionary values.
::

    self.write_orders =
    {'simple scan data':['data axis precedence','data axis id'],
     'simple detector axis vector mcstas':['frame axis location angular position'],
     'goniometer axis vector mcstas':['frame axis location angular position'],}


Step 5: Synthetic values
------------------------

Occasionally multiple items of information will be packed into a single format location.
The ``self.synthetic_values`` class variable is a dictionary of these local datanames.
The keys of the dictionary should be local datanames appearing in ``self.name_locations``,
and the values are ``([extracted datanames list],encoding_function,extraction function)``
tuples.
