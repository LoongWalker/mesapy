/**************************************************************/
 /***  C header subsection: RPython tracebacks for debugging ***/


/* We store a list of (location, exctype) in a circular buffer that
   we hope is large enough.  Example of how to interpret the content
   of the buffer:

       location   exctype      meaning

       NULL       &KeyError    a KeyError was raised
       h:5        NULL         it was raised at h:5
       g:12       NULL         which itself was called from g:12
       f:17       &KeyError    called from f:17, where a finally block starts
       ...                     ...more exceptions can occur...
       RERAISE    &KeyError    eventually the KeyError is re-raised by f
       entry:25   NULL         which itself was called from entry:25

   Note that decoding the buffer assumes that when exctype matches, it was
   really the same exception, for the purpose of going back from the RERAISE
   line to the f:17/KeyError line.
*/

#ifdef RPY_LL_ASSERT
#  define PYPY_DEBUG_TRACEBACK_DEPTH        8192    /* a power of two */
#else
#  define PYPY_DEBUG_TRACEBACK_DEPTH        128     /* a power of two */
#endif

#define PYPYDTPOS_RERAISE                 ((struct pypydtpos_s *) -1)
#define PYPYDTSTORE(loc, etype)                         \
  pypy_debug_tracebacks[pypydtcount].location = loc;    \
  pypy_debug_tracebacks[pypydtcount].exctype = etype;   \
  pypydtcount = (pypydtcount + 1) & (PYPY_DEBUG_TRACEBACK_DEPTH-1)

#define OP_DEBUG_START_TRACEBACK(etype, _)
#define OP_DEBUG_RERAISE_TRACEBACK(etp, _)
#define OP_DEBUG_PRINT_TRACEBACK()

#define PYPY_DEBUG_RECORD_TRACEBACK(funcname)
#define PYPY_DEBUG_CATCH_EXCEPTION(funcname, etype, is_fatal)
struct pypydtpos_s {
  const char *filename;
  const char *funcname;
  int lineno;
};

struct pypydtentry_s {
  struct pypydtpos_s *location;
  void *exctype;
};

RPY_EXTERN int pypydtcount;
RPY_EXTERN struct pypydtentry_s pypy_debug_tracebacks[PYPY_DEBUG_TRACEBACK_DEPTH];

RPY_EXTERN void pypy_debug_traceback_print(void);
RPY_EXTERN void pypy_debug_catch_fatal_exception(void);
