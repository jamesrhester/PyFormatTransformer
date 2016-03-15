PROGRAMS = nx_format_adapter.py cif_format_adapter.py TransformManager.py create_test_file.py TestGenericInput.py
documentation = INSTALLATION README How-To-Use.rst adding-new-datanames.rst adding-new-formats.rst LICENSE imgCIF_changes.txt
testfiles = testfiles/adsc_jrh_testfile.cif testfiles/nexus-multi-image.nx testfiles/multi-image-test.cif testfiles/nexus-multi-image.nx testfiles/adsc_jrh_testfile.nx testfiles/Cu033V2O5_1_001.cbf

programs: $(PROGRAMS)
#
%.py: %.ui
	pyside-uic -x -o $@ $< 
#
%.py: %.py.rst
	./pylit.py -t $< 
#
%.py: %.py.txt
	./pylit.py -t $<
#
clean:
	rm *.pyc

package: $(PROGRAMS) $(documentation) $(testfiles) full_demo_1.0.dic
	tar czvf FormatTransformer.tar.gz $^
#
