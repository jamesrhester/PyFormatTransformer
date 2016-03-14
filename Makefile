programs: nx_format_adapter.py cif_format_adapter.py TransformManager.py create_test_file.py

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
