"""fantasy_simulator.ui - CLI screen and display sub-package.

Sub-modules
-----------
screens          Screen / menu functions and simulation helpers.
ui_helpers       Display formatting and low-level input utilities.
ui_context       ``UIContext`` dependency container (``InputBackend`` +
                 ``RenderBackend``).
map_renderer     Map data extraction (``MapCellInfo``, ``MapRenderInfo``)
                 and ASCII rendering.
input_backend    ``InputBackend`` protocol + ``StdInputBackend``.
render_backend   ``RenderBackend`` protocol + ``PrintRenderBackend``.
"""
