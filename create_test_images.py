# Create the test images and output to minimal imgCIF file
# The text is provided as a raw PGM file.

import cif_format_adapter as cf
import PIL,numpy

def add_text_to_image(rawdata,textimagefile):
    """Add the text image from textimagefile into
    the image provided in rawdata"""
    textimage = PIL.Image.open(textimagefile)
    textdata = textimage.getdata()
    textarray = numpy.array(textdata)
    textarray.resize(rawdata.shape)
    outarray = rawdata + (textarray - 255)*-10
    return outarray

def input_starting_data(imgciffile):
    """Read images"""
    cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
    cfa.open_file(imgciffile)
    cfa.open_data_unit()
    images = cfa.get_by_location("2D data","Integer")
    return images

def output_finished_data(imgciffile,newimages):
    """Place the images in a new file"""
    cfa = cf.CifAdapter(cf.canonical_name_locations,cf.canonical_groupings)
    cfa.create_data_unit()
    cfa.set_by_location("2D data",newimages,"Integer")
    cfa.set_by_location("2D data identifier",range(1,len(newimages)+1),"Integer")
    cfa.set_by_location("2D data structure id",["array_1"]*len(newimages),"Text")
    cfa.close_data_unit()
    cfa.output_file(imgciffile)

def run_watermarking(infile,outfile):
    """Run the whole process"""
    in_images = input_starting_data(infile)
    small_images = [a[900:1100,850:1150] for a in in_images]
    word_files = ["testfiles/"+ a for a in ["this_image.pgm","is_image.pgm","not_image.pgm",
                  "an_image.pgm","image_image.pgm"]]
    watermarked = [add_text_to_image(a[0],a[1]) for a in zip(small_images,word_files)]
    output_finished_data(outfile,watermarked)
