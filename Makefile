MODULES = FormatTransformer/FormatAdapters/nx_format_adapter.py FormatTransformer/FormatAdapters/cif_format_adapter.py FormatTransformer/TransformManager.py FormatTransformer/create_test_file.py
documentation = INSTALLATION README documentation/How-To-Use.rst documentation/adding-new-datanames.rst documentation/adding-new-formats.rst LICENSE documentation/imgCIF_changes.txt
testfiles = FormatTransformer/testfiles/adsc_jrh_testfile.cif FormatTransformer/testfiles/nexus-multi-image.nx FormatTransformer/testfiles/multi-image-test.cif  FormatTransformer/testfiles/Cu033V2O5_1_001.cbf
Others = TestGenericInput.py

modules: $(MODULES)
#
%.py: %.py.rst
	./pylit.py -t $< 
#
%.py: %.py.txt
	./pylit.py -t $<
#
clean:
	rm *.pyc

package: $(MODULES) $(documentation) $(testfiles) full_demo_1.0.dic
	tar czvf PyFormatTransformer.tar.gz $^
#
