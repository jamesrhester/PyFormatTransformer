# Create the test file used in the NX testing, based on the CIF equivalent
import cif_format_adapter as cf
import nx_format_adapter as nx
import drive_transformation as d

bundle_names = ["full simple data scan id",
                "full simple data",
                "data axis id",
                "data axis precedence",
                "detector axis id",
                "detector axis vector mcstas",
                "detector axis offset mcstas",
                "incident wavelength",
                "wavelength id"]

f = open("data_bundle_names","w")
for bn in bundle_names: f.write(bn+"\n")
f.close()

d.manage_transform("data_bundle_names","cif","testfiles/multi-image-test.cif",
                   "nexus","testfiles/nexus-multi-image.nx")
