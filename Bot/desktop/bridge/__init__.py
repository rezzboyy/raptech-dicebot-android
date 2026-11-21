"""Bridge layer: menjembatani engine Python (corebot) ke Qt UI.

Semua interaksi GUI ke engine lewat sini. Engine tetap murni Python
(tidak tahu soal Qt); bridge yang mengubah event engine jadi Qt signal
supaya thread-safe untuk update UI di main thread.
"""
