programs: nx_format_adapter.py

#
%.py: %.ui
	pyside-uic -x -o $@ $< 
#
%.py: %.py.rst
	./pylit.py -t $< 
#
