def test_form_libs_import():
    import docx, docxtpl, openpyxl  # noqa: F401
    import agents.doc_generation, agents.doc_generation.fillers      # noqa: F401
