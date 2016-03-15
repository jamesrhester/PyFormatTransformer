How to Use This Software
------------------------

This software transforms data files created according to one standard into
data files conformant so some other standard which may use a different
file format. This procedure requires

(1) a DDLm dictionary containing definitions for the relevant canonical names,
    possibly including dREL algorithms relating canonical names to one another.

(2) format adapters for each of the formats. Format adapters should conform to
    the API described in [[adding-new-formats.rst]].

The software is bundled with demonstration format adapters for imgCIF
and the NeXus NXmx application definition, together with a DDLm dictionary.
Programmers are advised to consult the test routines in ``TestGenericInput.py``
for examples of use.

Step 1: Create the transform manager
------------------------------------
A TransformManager object is used to manage the overall transformation process.

::
    
    import TransformManager as t

    transformer = t.TransformManager()

Step 2: Register format adapters
--------------------------------

Each format adapter is provided as an object of the appropriate class.
This allows each adapter to be custom initialised. The adapter is
registered by providing the object and a simple identifying string.

::

    import nx_format_adapter as n
    nxmx = n.NXAdapter(n.canonical_groupings)
    transformer.register(nxmx,"nxmx")
    import cif_format_adapter as cf
    ccf = cf.CifAdapter(cf.canonical_groupings,cf.domain_names)
    transformer.register(ccf,"cif")

Step 3: Set the dictionary
--------------------------

Advise the transformer of the DDLm dictionary to use if an output
canonical name is not found in the input file.

::
    transformer.set_dictionary("full_demo_1.0.dic")

    
Step 4: Run the transformation
------------------------------

Provide a list of canonical names for the output file, together with
input and output filenames, specifying in each case the relevant
format.  The transformation manager will attempt to find or calculate
the items in the output bundle based on information in the dictionary.

::

    output_bundle = ["a different dataname","some other dataname","a dataname"]
    transformer.manage_transform(output_bundle,"input.nx","nxmx","output.cif","cif")


Notes
-----

Although the above interface provides ample opportunity for checking (e.g.
checking that canonical groupings match those provided in the dictionary,
checking that the API of the class matches the expected API) none is
currently performed.
