import sys
from pypy.interpreter.gateway import interp2app, unwrap_spec
from pypy.interpreter.baseobjspace import W_Root
from pypy.interpreter.typedef import TypeDef, interp_attrproperty
from pypy.interpreter.error import OperationError, oefmt
from rpython.rlib.rarithmetic import intmask, r_uint
from rpython.rlib.objectmodel import keepalive_until_here
from rpython.rtyper.lltypesystem import rffi

from rpython.rlib import rminiz_oxide


if intmask(2**31) == -2**31:
    # 32-bit platforms
    unsigned_to_signed_32bit = intmask
else:
    # 64-bit platforms
    def unsigned_to_signed_32bit(x):
        return intmask(rffi.cast(rffi.INT, x))


@unwrap_spec(string='bufferstr', start='truncatedint_w')
def crc32(space, string, start = rminiz_oxide.CRC32_DEFAULT_START):
    """
    crc32(string[, start]) -- Compute a CRC-32 checksum of string.

    An optional starting value can be specified.  The returned checksum is
    an integer.
    """
    ustart = r_uint(start)
    checksum = rminiz_oxide.crc32(string, ustart)

    # This is, perhaps, a little stupid.  zlib returns the checksum unsigned.
    # CPython exposes it as a signed value, though. -exarkun
    # Note that in CPython < 2.6 on 64-bit platforms the result is
    # actually unsigned, but it was considered to be a bug so we stick to
    # the 2.6 behavior and always return a number in range(-2**31, 2**31).
    checksum = unsigned_to_signed_32bit(checksum)

    return space.newint(checksum)


@unwrap_spec(string='bufferstr', start='truncatedint_w')
def adler32(space, string, start=rminiz_oxide.ADLER32_DEFAULT_START):
    """
    adler32(string[, start]) -- Compute an Adler-32 checksum of string.

    An optional starting value can be specified.  The returned checksum is
    an integer.
    """
    ustart = r_uint(start)
    checksum = rminiz_oxide.adler32(string, ustart)
    # See comments in crc32() for the following line
    checksum = unsigned_to_signed_32bit(checksum)

    return space.newint(checksum)


class Cache:
    def __init__(self, space):
        self.w_error = space.new_exception_class("zlib.error")

def zlib_error(space, msg):
    w_error = space.fromcache(Cache).w_error
    return OperationError(w_error, space.newtext(msg))


@unwrap_spec(string='bufferstr', level=int)
def compress(space, string, level=rminiz_oxide.Z_DEFAULT_COMPRESSION):
    """
    compress(string[, level]) -- Returned compressed string.

    Optional arg level is the compression level, in 1-9.
    """
    try:
        try:
            stream = rminiz_oxide.deflateInit(level)
        except ValueError:
            raise zlib_error(space, "Bad compression level")
        try:
            result = rminiz_oxide.compress(stream, string, rminiz_oxide.Z_FINISH)
        finally:
            rminiz_oxide.deflateEnd(stream)
    except rminiz_oxide.RZlibError as e:
        raise zlib_error(space, e.msg)
    return space.newbytes(result)


@unwrap_spec(string='bufferstr', wbits="c_int", bufsize=int)
def decompress(space, string, wbits=rminiz_oxide.MAX_WBITS, bufsize=0):
    """
    decompress(string[, wbits[, bufsize]]) -- Return decompressed string.

    Optional arg wbits is the window buffer size.  Optional arg bufsize is
    only for compatibility with CPython and is ignored.
    """
    try:
        try:
            stream = rminiz_oxide.inflateInit(wbits)
        except ValueError:
            raise zlib_error(space, "Bad window buffer size")
        try:
            result, _, _ = rminiz_oxide.decompress(stream, string, rminiz_oxide.Z_FINISH)
        finally:
            rminiz_oxide.inflateEnd(stream)
    except rminiz_oxide.RZlibError as e:
        raise zlib_error(space, e.msg)
    return space.newbytes(result)


class ZLibObject(W_Root):
    """
    Common base class for Compress and Decompress.
    """
    stream = rminiz_oxide.null_stream

    def __init__(self, space):
        self._lock = space.allocate_lock()

    def lock(self):
        """To call before using self.stream."""
        self._lock.acquire(True)

    def unlock(self):
        """To call after using self.stream."""
        self._lock.release()
        keepalive_until_here(self)
        # subtle: we have to make sure that 'self' is not garbage-collected
        # while we are still using 'self.stream' - hence the keepalive.


class Compress(ZLibObject):
    """
    Wrapper around zlib's z_stream structure which provides convenient
    compression functionality.
    """
    def __init__(self, space, level=rminiz_oxide.Z_DEFAULT_COMPRESSION,
                 method=rminiz_oxide.Z_DEFLATED,             # \
                 wbits=rminiz_oxide.MAX_WBITS,               #  \   undocumented
                 memLevel=rminiz_oxide.DEF_MEM_LEVEL,        #  /    parameters
                 strategy=rminiz_oxide.Z_DEFAULT_STRATEGY):  # /
        ZLibObject.__init__(self, space)
        try:
            self.stream = rminiz_oxide.deflateInit(level, method, wbits,
                                            memLevel, strategy)
        except rminiz_oxide.RZlibError as e:
            raise zlib_error(space, e.msg)
        except ValueError:
            raise oefmt(space.w_ValueError, "Invalid initialization option")
        self.register_finalizer(space)

    def _finalize_(self):
        """Automatically free the resources used by the stream."""
        if self.stream:
            rminiz_oxide.deflateEnd(self.stream)
            self.stream = rminiz_oxide.null_stream

    @unwrap_spec(data='bufferstr')
    def compress(self, space, data):
        """
        compress(data) -- Return a string containing data compressed.

        After calling this function, some of the input data may still be stored
        in internal buffers for later processing.

        Call the flush() method to clear these buffers.
        """
        try:
            self.lock()
            try:
                if not self.stream:
                    raise zlib_error(space,
                                     "compressor object already flushed")
                result = rminiz_oxide.compress(self.stream, data)
            finally:
                self.unlock()
        except rminiz_oxide.RZlibError as e:
            raise zlib_error(space, e.msg)
        return space.newbytes(result)

    @unwrap_spec(mode="c_int")
    def flush(self, space, mode=rminiz_oxide.Z_FINISH):
        """
        flush( [mode] ) -- Return a string containing any remaining compressed
        data.

        mode can be one of the constants Z_SYNC_FLUSH, Z_FULL_FLUSH, Z_FINISH;
        the default value used when mode is not specified is Z_FINISH.

        If mode == Z_FINISH, the compressor object can no longer be used after
        calling the flush() method.  Otherwise, more data can still be
        compressed.
        """
        try:
            self.lock()
            try:
                if not self.stream:
                    raise zlib_error(space,
                                     "compressor object already flushed")
                result = rminiz_oxide.compress(self.stream, '', mode)
                if mode == rminiz_oxide.Z_FINISH:    # release the data structures now
                    rminiz_oxide.deflateEnd(self.stream)
                    self.stream = rminiz_oxide.null_stream
                    self.may_unregister_rpython_finalizer(space)
            finally:
                self.unlock()
        except rminiz_oxide.RZlibError as e:
            raise zlib_error(space, e.msg)
        return space.newbytes(result)


@unwrap_spec(level=int, method=int, wbits=int, memLevel=int, strategy=int)
def Compress___new__(space, w_subtype, level=rminiz_oxide.Z_DEFAULT_COMPRESSION,
                     method=rminiz_oxide.Z_DEFLATED,             # \
                     wbits=rminiz_oxide.MAX_WBITS,               #  \   undocumented
                     memLevel=rminiz_oxide.DEF_MEM_LEVEL,        #  /    parameters
                     strategy=rminiz_oxide.Z_DEFAULT_STRATEGY):  # /
    """
    Create a new z_stream and call its initializer.
    """
    stream = space.allocate_instance(Compress, w_subtype)
    stream = space.interp_w(Compress, stream)
    Compress.__init__(stream, space, level,
                      method, wbits, memLevel, strategy)
    return stream


Compress.typedef = TypeDef(
    'Compress',
    __new__ = interp2app(Compress___new__),
    compress = interp2app(Compress.compress),
    flush = interp2app(Compress.flush),
    __doc__ = """compressobj([level]) -- Return a compressor object.

Optional arg level is the compression level, in 1-9.
""")


class Decompress(ZLibObject):
    """
    Wrapper around zlib's z_stream structure which provides convenient
    decompression functionality.
    """
    def __init__(self, space, wbits=rminiz_oxide.MAX_WBITS):
        """
        Initialize a new decompression object.

        wbits is an integer between 8 and MAX_WBITS or -8 and -MAX_WBITS
        (inclusive) giving the number of "window bits" to use for compression
        and decompression.  See the documentation for deflateInit2 and
        inflateInit2.
        """
        ZLibObject.__init__(self, space)
        self.unused_data = ''
        self.unconsumed_tail = ''
        try:
            self.stream = rminiz_oxide.inflateInit(wbits)
        except rminiz_oxide.RZlibError as e:
            raise zlib_error(space, e.msg)
        except ValueError:
            raise oefmt(space.w_ValueError, "Invalid initialization option")
        self.register_finalizer(space)

    def _finalize_(self):
        """Automatically free the resources used by the stream."""
        if self.stream:
            rminiz_oxide.inflateEnd(self.stream)
            self.stream = rminiz_oxide.null_stream

    def _save_unconsumed_input(self, data, finished, unused_len):
        unused_start = len(data) - unused_len
        assert unused_start >= 0
        tail = data[unused_start:]
        if finished:
            self.unconsumed_tail = ''
            self.unused_data += tail
        else:
            self.unconsumed_tail = tail

    @unwrap_spec(data='bufferstr', max_length=int)
    def decompress(self, space, data, max_length=0):
        """
        decompress(data[, max_length]) -- Return a string containing the
        decompressed version of the data.

        If the max_length parameter is specified then the return value will be
        no longer than max_length.  Unconsumed input data will be stored in the
        unconsumed_tail attribute.
        """
        if max_length == 0:
            max_length = sys.maxint
        elif max_length < 0:
            raise oefmt(space.w_ValueError,
                        "max_length must be greater than zero")
        try:
            self.lock()
            try:
                result = rminiz_oxide.decompress(self.stream, data, max_length=max_length)
            finally:
                self.unlock()
        except rminiz_oxide.RZlibError as e:
            raise zlib_error(space, e.msg)

        string, finished, unused_len = result
        self._save_unconsumed_input(data, finished, unused_len)
        return space.newbytes(string)

    def flush(self, space, w_length=None):
        """
        flush( [length] ) -- This is kept for backward compatibility,
        because each call to decompress() immediately returns as much
        data as possible.
        """
        if w_length is not None:
            length = space.int_w(w_length)
            if length <= 0:
                raise oefmt(space.w_ValueError,
                            "length must be greater than zero")
        data = self.unconsumed_tail
        try:
            self.lock()
            try:
                result = rminiz_oxide.decompress(self.stream, data, rminiz_oxide.Z_FINISH)
            finally:
                self.unlock()
        except rminiz_oxide.RZlibError:
            string = ""
        else:
            string, finished, unused_len = result
            self._save_unconsumed_input(data, finished, unused_len)
        return space.newbytes(string)


@unwrap_spec(wbits=int)
def Decompress___new__(space, w_subtype, wbits=rminiz_oxide.MAX_WBITS):
    """
    Create a new Decompress and call its initializer.
    """
    stream = space.allocate_instance(Decompress, w_subtype)
    stream = space.interp_w(Decompress, stream)
    Decompress.__init__(stream, space, wbits)
    return stream


Decompress.typedef = TypeDef(
    'Decompress',
    __new__ = interp2app(Decompress___new__),
    decompress = interp2app(Decompress.decompress),
    flush = interp2app(Decompress.flush),
    unused_data = interp_attrproperty('unused_data', Decompress, wrapfn="newbytes"),
    unconsumed_tail = interp_attrproperty('unconsumed_tail', Decompress, wrapfn="newbytes"),
    __doc__ = """decompressobj([wbits]) -- Return a decompressor object.

Optional arg wbits is the window buffer size.
""")
