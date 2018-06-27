
"""
Tests for the rminiz_oxide module.
"""

import py, sys
from rpython.rlib import rminiz_oxide
from rpython.rlib.rarithmetic import r_uint
from rpython.rlib import clibffi # for side effect of testing lib_c_name on win32
import zlib

expanded = 'some bytes which will be compressed'
compressed = zlib.compress(expanded)


def test_crc32():
    """
    When called with a string, rminiz_oxide.crc32 should compute its CRC32 and
    return it as a unsigned 32 bit integer.
    """
    assert rminiz_oxide.crc32('') == r_uint(0)
    assert rminiz_oxide.crc32('\0') == r_uint(3523407757)
    assert rminiz_oxide.crc32('hello, world.') == r_uint(3358036098)


def test_crc32_start_value():
    """
    When called with a string and an integer, zlib.crc32 should compute the
    CRC32 of the string using the integer as the starting value.
    """
    assert rminiz_oxide.crc32('', 42) == r_uint(42)
    assert rminiz_oxide.crc32('\0', 42) == r_uint(163128923)
    assert rminiz_oxide.crc32('hello, world.', 42) == r_uint(1090960721)
    hello = 'hello, '
    hellocrc = rminiz_oxide.crc32(hello)
    world = 'world.'
    helloworldcrc = rminiz_oxide.crc32(world, hellocrc)
    assert helloworldcrc == rminiz_oxide.crc32(hello + world)


def test_adler32():
    """
    When called with a string, zlib.crc32 should compute its adler 32
    checksum and return it as an unsigned 32 bit integer.
    """
    assert rminiz_oxide.adler32('') == r_uint(1)
    assert rminiz_oxide.adler32('\0') == r_uint(65537)
    assert rminiz_oxide.adler32('hello, world.') == r_uint(571147447)
    assert rminiz_oxide.adler32('x' * 23) == r_uint(2172062409)


def test_adler32_start_value():
    """
    When called with a string and an integer, zlib.adler32 should compute
    the adler 32 checksum of the string using the integer as the starting
    value.
    """
    assert rminiz_oxide.adler32('', 42) == r_uint(42)
    assert rminiz_oxide.adler32('\0', 42) == r_uint(2752554)
    assert rminiz_oxide.adler32('hello, world.', 42) == r_uint(606078176)
    assert rminiz_oxide.adler32('x' * 23, 42) == r_uint(2233862898)
    hello = 'hello, '
    hellosum = rminiz_oxide.adler32(hello)
    world = 'world.'
    helloworldsum = rminiz_oxide.adler32(world, hellosum)
    assert helloworldsum == rminiz_oxide.adler32(hello + world)


def test_invalidLevel():
    """
    deflateInit() should raise ValueError when an out of bounds level is
    passed to it.
    """
    py.test.raises(ValueError, rminiz_oxide.deflateInit, -2)
    py.test.raises(ValueError, rminiz_oxide.deflateInit, 10)


def test_deflate_init_end():
    """
    deflateInit() followed by deflateEnd() should work and do nothing.
    """
    stream = rminiz_oxide.deflateInit()
    rminiz_oxide.deflateEnd(stream)


# miniz_oxide currently does not support setting dictionary
#
# def test_deflate_set_dictionary():
#     text = 'abcabc'
#     zdict = 'abc'
#     stream = rminiz_oxide.deflateInit()
#     rminiz_oxide.deflateSetDictionary(stream, zdict)
#     bytes = rminiz_oxide.compress(stream, text, rminiz_oxide.Z_FINISH)
#     rminiz_oxide.deflateEnd(stream)
#     
#     stream2 = rminiz_oxide.inflateInit()
# 
#     from rpython.rtyper.lltypesystem import lltype, rffi, rstr
#     from rpython.rtyper.annlowlevel import llstr
#     from rpython.rlib.rstring import StringBuilder
#     with lltype.scoped_alloc(rffi.CCHARP.TO, len(bytes)) as inbuf:
#         rstr.copy_string_to_raw(llstr(bytes), inbuf, 0, len(bytes))
#         stream2.c_next_in = rffi.cast(rminiz_oxide.Bytefp, inbuf)
#         rffi.setintfield(stream2, 'c_avail_in', len(bytes))
#         with lltype.scoped_alloc(rffi.CCHARP.TO, 100) as outbuf:
#             stream2.c_next_out = rffi.cast(rminiz_oxide.Bytefp, outbuf)
#             bufsize = 100
#             rffi.setintfield(stream2, 'c_avail_out', bufsize)
#             err = rminiz_oxide._inflate(stream2, rminiz_oxide.Z_SYNC_FLUSH)
#             assert err == rminiz_oxide.Z_NEED_DICT
#             rminiz_oxide.inflateSetDictionary(stream2, zdict)
#             rminiz_oxide._inflate(stream2, rminiz_oxide.Z_SYNC_FLUSH)
#             avail_out = rffi.cast(lltype.Signed, stream2.c_avail_out)
#             result = StringBuilder()
#             result.append_charpsize(outbuf, bufsize - avail_out)
# 
#     rminiz_oxide.inflateEnd(stream2)
#     assert result.build() == text


def test_compression():
    """
    Once we have got a deflate stream, rminiz_oxide.compress() 
    should allow us to compress bytes.
    """
    stream = rminiz_oxide.deflateInit()
    bytes = rminiz_oxide.compress(stream, expanded)
    bytes += rminiz_oxide.compress(stream, "", rminiz_oxide.Z_FINISH)
    rminiz_oxide.deflateEnd(stream)
    assert bytes == compressed


def test_compression_lots_of_data():
    """
    Test compression of more data that fits in a single internal output buffer.
    """
    expanded = repr(range(20000))
    compressed = zlib.compress(expanded)
    print len(expanded), '=>', len(compressed)
    stream = rminiz_oxide.deflateInit()
    bytes = rminiz_oxide.compress(stream, expanded, rminiz_oxide.Z_FINISH)
    rminiz_oxide.deflateEnd(stream)
    assert bytes == compressed


def test_inflate_init_end():
    """
    inflateInit() followed by inflateEnd() should work and do nothing.
    """
    stream = rminiz_oxide.inflateInit()
    rminiz_oxide.inflateEnd(stream)


def test_decompression():
    """
    Once we have got a inflate stream, rminiz_oxide.decompress()
    should allow us to decompress bytes.
    """
    stream = rminiz_oxide.inflateInit()
    bytes1, finished1, unused1 = rminiz_oxide.decompress(stream, compressed)
    bytes2, finished2, unused2 = rminiz_oxide.decompress(stream, "", rminiz_oxide.Z_FINISH)
    rminiz_oxide.inflateEnd(stream)
    assert bytes1 + bytes2 == expanded
    assert finished1 is True
    assert finished2 is True
    assert unused1 == 0
    assert unused2 == 0


def test_decompression_lots_of_data():
    """
    Test compression of more data that fits in a single internal output buffer.
    """
    expanded = repr(range(20000))
    compressed = zlib.compress(expanded)
    print len(compressed), '=>', len(expanded)
    stream = rminiz_oxide.inflateInit()
    bytes, finished, unused = rminiz_oxide.decompress(stream, compressed,
                                               rminiz_oxide.Z_FINISH)
    rminiz_oxide.inflateEnd(stream)
    assert bytes == expanded
    assert finished is True
    assert unused == 0


def test_decompression_truncated_input():
    """
    Test that we can accept incomplete input when inflating, but also
    detect this situation when using Z_FINISH.
    """
    expanded = repr(range(20000))
    compressed = zlib.compress(expanded)
    print len(compressed), '=>', len(expanded)
    stream = rminiz_oxide.inflateInit()
    data, finished1, unused1 = rminiz_oxide.decompress(stream, compressed[:1000])
    assert expanded.startswith(data)
    assert finished1 is False
    assert unused1 == 0
    data2, finished2, unused2 = rminiz_oxide.decompress(stream, compressed[1000:2000])
    data += data2
    assert finished2 is False
    assert unused2 == 0
    assert expanded.startswith(data)
    exc = py.test.raises(
        rminiz_oxide.RZlibError,
        rminiz_oxide.decompress, stream, compressed[2000:-500], rminiz_oxide.Z_FINISH)
    msg = "Error -5 while decompressing data: incomplete or truncated stream"
    assert str(exc.value) == msg
    rminiz_oxide.inflateEnd(stream)


def test_decompression_too_much_input():
    """
    Check the case where we feed extra data to decompress().
    """
    stream = rminiz_oxide.inflateInit()
    data1, finished1, unused1 = rminiz_oxide.decompress(stream, compressed[:-5])
    assert finished1 is False
    assert unused1 == 0
    data2, finished2, unused2 = rminiz_oxide.decompress(stream,
                                                 compressed[-5:] + 'garbage')
    assert finished2 is True
    assert unused2 == len('garbage')
    assert data1 + data2 == expanded
    data3, finished3, unused3 = rminiz_oxide.decompress(stream, 'more_garbage')
    assert finished3 is True
    assert unused3 == len('more_garbage')
    assert data3 == ''

    rminiz_oxide.inflateEnd(stream)


def test_decompress_max_length():
    """
    Test the max_length argument of decompress().
    """
    stream = rminiz_oxide.inflateInit()
    data1, finished1, unused1 = rminiz_oxide.decompress(stream, compressed,
                                                 max_length = 17)
    assert data1 == expanded[:17]
    assert finished1 is False
    assert unused1 > 0
    data2, finished2, unused2 = rminiz_oxide.decompress(stream, compressed[-unused1:])
    assert data2 == expanded[17:]
    assert finished2 is True
    assert unused2 == 0

    rminiz_oxide.inflateEnd(stream)


def test_cornercases():
    """
    Test degenerate arguments.
    """
    stream = rminiz_oxide.deflateInit()
    bytes = rminiz_oxide.compress(stream, "")
    bytes += rminiz_oxide.compress(stream, "")
    bytes += rminiz_oxide.compress(stream, "", rminiz_oxide.Z_FINISH)
    assert zlib.decompress(bytes) == ""
    rminiz_oxide.deflateEnd(stream)

    stream = rminiz_oxide.inflateInit()
    data, finished, unused = rminiz_oxide.decompress(stream, "")
    assert data == ""
    assert finished is False
    assert unused == 0
    buf = compressed
    for i in range(10):
        data, finished, unused = rminiz_oxide.decompress(stream, buf, max_length=0)
        assert data == ""
        assert finished is False
        assert unused > 0
        buf = buf[-unused:]
    rminiz_oxide.inflateEnd(stream)

# rminiz_oxide doesn't provide this API right now.
#
# def test_zlibVersion():
#     runtime_version = rminiz_oxide.zlibVersion()
#     assert runtime_version[0] == rminiz_oxide.ZLIB_VERSION[0]

def test_translate_and_large_input():
    from rpython.translator.c.test.test_genc import compile

    def f(i, check):
        bytes = "s" * i
        if check == 1:
            for j in range(3):
                stream = rminiz_oxide.deflateInit()
                bytes = rminiz_oxide.compress(stream, bytes, rminiz_oxide.Z_FINISH)
                rminiz_oxide.deflateEnd(stream)
            return bytes
        if check == 2:
            return str(rminiz_oxide.adler32(bytes))
        if check == 3:
            return str(rminiz_oxide.crc32(bytes))
        return '?'

    fc = compile(f, [int, int])

    test_list = [1, 2, 3, 5, 8, 87, 876, 8765, 87654, 876543, 8765432,
                 127329129]       # up to ~128MB
    if sys.maxint > 2**32:
        test_list.append(4305704715)    # 4.01GB
        # XXX should we have a way to say "I don't have enough RAM,
        # don't run this"?

    for a in test_list:
        print 'Testing compression of "s" * %d' % a
        z = zlib.compressobj()
        count = a
        pieces = []
        while count > 1024*1024:
            pieces.append(z.compress("s" * (1024*1024)))
            count -= 1024*1024
        pieces.append(z.compress("s" * count))
        pieces.append(z.flush(zlib.Z_FINISH))
        expected = ''.join(pieces)
        del pieces
        expected = zlib.compress(expected)
        expected = zlib.compress(expected)
        assert fc(a, 1) == expected

        print 'Testing adler32 and crc32 of "s" * %d' % a
        def compute(function, start):
            count = a
            while count > 0:
                count1 = min(count, 1024*1024)
                start = function("s" * count1, start)
                count -= count1
            return start
        expected_adler32 = compute(zlib.adler32, 1) & (2**32-1)
        expected_crc32 = compute(zlib.crc32, 0) & (2**32-1)
        assert fc(a, 2) == str(expected_adler32)
        assert fc(a, 3) == str(expected_crc32)
