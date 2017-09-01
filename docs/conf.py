# -*- coding: utf-8 -*-

import sphinx_rtd_theme


# -- General configuration ------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
]

autodoc_default_flags = [
    'members',
    'private-members',
    'inherited-members',
    'show-inheritance',
]
autoclass_content = 'both'

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = u'HoneyBadgerBFT'
copyright = u'2017, Andrew Miller et al.'
author = u'Andrew Miller et al.'
version = u'0.1'
release = u'0.1.0'
language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'
todo_include_todos = True


# -- Options for HTML output ----------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',  # needs 'show_related': True theme option to display
        'searchbox.html',
        'donate.html',
    ]
}


# -- Options for HTMLHelp output ------------------------------------------

htmlhelp_basename = 'HoneyBadgerBFTdoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {}
latex_documents = [
    (master_doc, 'HoneyBadgerBFT.tex', u'HoneyBadgerBFT Documentation',
     u'Andrew Miller et al.', 'manual'),
]


# -- Options for manual page output ---------------------------------------

man_pages = [
    (master_doc, 'honeybadgerbft', u'HoneyBadgerBFT Documentation',
     [author], 1)
]


# -- Options for Texinfo output -------------------------------------------

texinfo_documents = [
    (master_doc, 'HoneyBadgerBFT', u'HoneyBadgerBFT Documentation',
     author, 'HoneyBadgerBFT', 'One line description of project.',
     'Miscellaneous'),
]


intersphinx_mapping = {'https://docs.python.org/': None}
