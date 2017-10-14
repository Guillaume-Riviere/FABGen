import gen


#
class PythonTypeConverterCommon(gen.TypeConverter):
	def __init__(self, type, arg_storage_type=None, bound_name=None, rval_storage_type=None):
		super().__init__(type, arg_storage_type, bound_name, rval_storage_type)

	def get_type_api(self, module_name):
		return '// type API for %s\n' % self.ctype +\
		'bool check_%s(PyObject *o);\n' % self.bound_name +\
		'void to_c_%s(PyObject *o, void *obj);\n' % self.bound_name +\
		'PyObject *from_c_%s(void *obj, OwnershipPolicy);\n' % self.bound_name +\
		'\n'

	def to_c_call(self, in_var, out_var_p):
		return 'to_c_%s(%s, (void *)%s);\n' % (self.bound_name, in_var, out_var_p)

	def from_c_call(self, out_var, expr, ownership):
		return "%s = from_c_%s((void *)%s, %s);\n" % (out_var, self.bound_name, expr, ownership)

	def check_call(self, in_var):
		return "check_%s(%s)" % (self.bound_name, in_var)


#
class PythonClassTypeDefaultConverter(PythonTypeConverterCommon):
	def __init__(self, type, arg_storage_type=None, bound_name=None, rval_storage_type=None):
		super().__init__(type, arg_storage_type, bound_name, rval_storage_type)

	def get_type_glue(self, gen, module_name):
		out = ''

		# repr feature support
		has_repr = 'repr' in self._features

		if has_repr:
			repr = self._features['repr']

			out += 'static PyObject *%s_tp_repr(PyObject *self) {\n' % self.bound_name
			out += '	std::string repr;\n'
			out += gen._prepare_c_arg_self(self, '_self')
			out += repr.get_repr('_self', 'repr')
			out += '	return PyUnicode_FromString(repr.c_str());\n'
			out += '}\n\n'

		# sequence feature support
		has_sequence = 'sequence' in self._features

		if has_sequence:
			out += '// sequence protocol for %s\n' % self.bound_name
			seq = self._features['sequence']

			# get_size
			out += 'static Py_ssize_t %s_sq_length(PyObject *self) {\n' % self.bound_name
			out += gen._prepare_c_arg_self(self, '_self')
			out += '	Py_ssize_t size = -1;\n'
			out += seq.get_size('_self', 'size')
			out += '	return size;\n'
			out += '}\n\n'

			# get_item
			out += 'static PyObject *%s_sq_item(PyObject *self, Py_ssize_t idx) {\n' % self.bound_name
			out += gen._prepare_c_arg_self(self, '_self')
			out += gen.decl_var(seq.wrapped_conv.ctype, 'rval')
			out += 'bool error = false;\n'
			out += seq.get_item('_self', 'idx', 'rval', 'error')
			out += '''if (error) {
	PyErr_Format(PyExc_IndexError, "invalid lookup");
	return NULL;
}\n'''
			out += gen.prepare_c_rval(seq.wrapped_conv, seq.wrapped_conv.ctype, 'rval')
			out += gen.commit_rvals(['rval'])
			out += '}\n\n'

			# set_item
			out += 'static int %s_sq_ass_item(PyObject *self, Py_ssize_t idx, PyObject *val) {\n' % self.bound_name
			out += '	if (!%s) {\n' % seq.wrapped_conv.check_call('val')
			out += '		PyErr_Format(PyExc_TypeError, "invalid type in assignation, expected %s");\n' % seq.wrapped_conv.ctype
			out += '		return -1;\n'
			out += '	}\n\n'
			out += gen._prepare_c_arg_self(self, '_self')
			out += gen._prepare_c_arg(0, seq.wrapped_conv, 'cval', 'setter')
			out += 'bool error = false;\n'
			out += seq.set_item('_self', 'idx', 'cval', 'error')
			out += '''if (error) {
	PyErr_Format(PyExc_IndexError, "invalid assignation");
	return -1;
}\n'''
			out += '	return 0;\n'
			out += '}\n\n'

		# type
		out += '// type %s\n' % self.bound_name
		out += 'static PyObject *%s_type;\n\n' % self.bound_name

		# constructor
		out += 'static PyObject *%s_tp_new(PyTypeObject *subtype, PyObject *args, PyObject *kwds) {\n' % self.bound_name
		if self._inline:
			out += '	assert(sizeof(%s) <= 16);\n\n' % self.ctype
		if self.constructor:
			out += '	return %s(NULL, args);\n' % self.constructor['proxy_name']
		else:
			out += '	PyErr_Format(PyExc_TypeError, "cannot create %s instances");\n' % self.bound_name
			out += '	return NULL;\n'
		out += '}\n\n'

		# members
		out += 'static PyGetSetDef %s_tp_getset[] = {\n' % self.bound_name
		for member in self.get_all_members():
			setter = member['setter']
			if setter is None:
				setter = 'NULL'
			out += '	{"%s", (getter)%s, (setter)%s, "TODO doc"},\n' % (member['name'], member['getter'], setter)
		out += '	{NULL} /* Sentinel */\n'
		out += '};\n\n'

		# output binding code for static class members
		static_members = self.get_all_static_members()

		if len(static_members) > 0:
			out += 'static void bind_%s_static_members(PyObject *o) {\n' % self.bound_name
			out += '	PyObject *tmp;\n\n'

			for i, attr in enumerate(static_members):
				if attr['getter']:
					out += '	// %s::%s\n' % (self.ctype, attr['name'])
					out += '	tmp = %s(o, NULL);\n' % attr['getter']
					out += '	PyObject_SetAttrString(o, "%s", tmp);\n' % attr['name']
					out += '	Py_DECREF(tmp);\n'
			out += '}\n\n'

		# methods
		out += 'static PyMethodDef %s_tp_methods[] = {\n' % self.bound_name
		for method in self.get_all_methods():
			out += '	{"%s", (PyCFunction)%s, METH_VARARGS},\n' % (method['bound_name'], method['proxy_name'])
		for method in self.get_all_static_methods():
			out += '	{"%s", (PyCFunction)%s, METH_VARARGS|METH_STATIC},\n' % (method['bound_name'], method['proxy_name'])
		out += '	{NULL} /* Sentinel */\n'
		out += '};\n\n'

		# comparison operators dispatcher
		def output_default_op_proxy(name, op):
			out = '''\
static PyObject *%s_default_Py_%s(PyObject *o1, PyObject *o2) {
	wrapped_Object *w1 = cast_to_wrapped_Object_safe(o1);
	wrapped_Object *w2 = cast_to_wrapped_Object_safe(o2);

	if (!w1 || !w2 || w1->type_tag != w2->type_tag) {
		Py_RETURN_FALSE;
	}
''' % (self.bound_name, name)

			if self._inline:
				out += '''
	if (*(%s *)w1->inline_obj %s *(%s *)w2->inline_obj) {
		Py_RETURN_FALSE;
	}
''' % (self.ctype, op, self.ctype)
			else:
				out += '''
	if (!(w1->obj %s w2->obj)) {
		Py_RETURN_FALSE;
	}
''' % op

			out += '''
	Py_RETURN_TRUE;
}
'''
			return out

		op_to_py_op = {'<': 'Py_LT', '<=': 'Py_LE', '==': 'Py_EQ', '!=': 'Py_NE', '>': 'Py_GT', '>=': 'Py_GE'}

		out += output_default_op_proxy('EQ', '==')
		out += output_default_op_proxy('NE', '!=')

		out += 'static PyObject *%s_tp_richcompare(PyObject *o1, PyObject *o2, int op) {\n' % self.bound_name
		for i, ops in enumerate(self.comparison_ops):
			out += "	if (op == %s) return %s(o1, o2);\n" % (op_to_py_op[ops['op']], ops['proxy_name'])
		if '==' not in self.comparison_ops:
			out += "	if (op == Py_EQ) return %s_default_Py_EQ(o1, o2);\n" % self.bound_name
		if '!=' not in self.comparison_ops:
			out += "	if (op == Py_NE) return %s_default_Py_NE(o1, o2);\n" % self.bound_name
		out += '	Py_RETURN_NOTIMPLEMENTED;\n'
		out += '}\n\n'

		# slots
		def get_operator_slot(slot, op):
			op = self.get_operator(op)
			return '	{%s, (void *)&%s},\n' % (slot, op['proxy_name']) if op else ''

		out += 'static PyType_Slot %s_slots[] = {\n' % self.bound_name
		out += '	{Py_tp_new, (void *)&%s_tp_new},\n' % self.bound_name
		out += '	{Py_tp_doc, (void *)"TODO doc"},\n'
		out += '	{Py_tp_dealloc, (void *)&wrapped_Object_tp_dealloc},\n'
		out += '	{Py_tp_getset, (void *)&%s_tp_getset},\n' % self.bound_name
		out += '	{Py_tp_methods, (void *)&%s_tp_methods},\n' % self.bound_name
		out += '	{Py_tp_richcompare, (void *)&%s_tp_richcompare},\n' % self.bound_name
		if has_repr:
			out += '	{Py_tp_repr, (void *)&%s_tp_repr},\n' % self.bound_name
		out += get_operator_slot('Py_nb_add', '+')
		out += get_operator_slot('Py_nb_subtract', '-')
		out += get_operator_slot('Py_nb_multiply', '*')
		out += get_operator_slot('Py_nb_true_divide', '/')
		if has_sequence:
			out += '	{Py_sq_length, (void *)&%s_sq_length},\n' % self.bound_name
			out += '	{Py_sq_item, (void *)&%s_sq_item},\n' % self.bound_name
			out += '	{Py_sq_ass_item, (void *)&%s_sq_ass_item},\n' % self.bound_name
		out += '''	{0, NULL}
};
\n'''

		# specification
		out += '''static PyType_Spec %s_spec = {
	"%s", /* name */
	sizeof(wrapped_Object), /* basicsize */
	0, /* itemsize*/
	Py_TPFLAGS_DEFAULT, /* flags */
	%s_slots
};
\n''' % (self.bound_name, self.bound_name, self.bound_name)

		# delete delegate
		out += 'static void delete_%s(void *o) { delete (%s *)o; }\n\n' % (self.bound_name, self.ctype)

		# check
		out += '''bool check_%s(PyObject *o) {
	wrapped_Object *w = cast_to_wrapped_Object_safe(o);
	if (!w)
		return false;
	return _type_tag_can_cast(w->type_tag, %s);
}
\n''' % (self.bound_name, self.type_tag)

		# to C
		out += '''void to_c_%s(PyObject *o, void *obj) {
	wrapped_Object *w = cast_to_wrapped_Object_unsafe(o);
	*(void **)obj = _type_tag_cast(w->obj, w->type_tag, %s);
}
\n''' % (self.bound_name, self.type_tag)

		# from C
		is_inline = False
		if self._non_copyable:
			if self._moveable:
				copy_code = 'obj = new %s(std::move(*(%s *)obj));' % (self.ctype, self.ctype)
			else:
				copy_code = '''PyErr_SetString(PyExc_RuntimeError, "type %s is non-copyable and non-moveable");
		return NULL;''' % self.bound_name
		else:
			if self._inline:
				is_inline = True
				copy_code = 'obj = new((void *)pyobj->inline_obj) %s(*(%s *)obj);' % (self.ctype, self.ctype)
			else:
				copy_code = 'obj = new %s(*(%s *)obj);' % (self.ctype, self.ctype)

		if is_inline:
			delete_code = 'pyobj->on_delete = &delete_inline_%s;' % self.bound_name
		else:
			delete_code = 'pyobj->on_delete = &delete_%s;' % self.bound_name

		if is_inline:
			out += '''
static void delete_inline_%s(void *o) {
	using T = %s;
	((T*)o)->~T();
}\n\n''' % (self.bound_name, self.ctype)

		out += '''PyObject *from_c_%s(void *obj, OwnershipPolicy own) {
	wrapped_Object *pyobj = PyObject_New(wrapped_Object, (PyTypeObject *)%s_type);
	if (own == Copy) {
		%s
	}
	init_wrapped_Object(pyobj, %s, obj);
	if (own != NonOwning)
		%s
	return (PyObject *)pyobj;
}
\n''' % (self.bound_name, self.bound_name, copy_code, self.type_tag, delete_code)

		return out

	def finalize_type(self):
		out = '	%s_type = PyType_FromSpec(&%s_spec);\n' % (self.bound_name, self.bound_name)
		if len(self.get_all_static_members()) > 0:
			out += '	bind_%s_static_members(%s_type);\n' % (self.bound_name, self.bound_name)
		out += '	PyModule_AddObject(m, "%s", %s_type);\n' % (self.bound_name, self.bound_name)
		return out


#
class PythonPtrTypeDefaultConverter(PythonTypeConverterCommon):
	def __init__(self, type, arg_storage_type=None, bound_name=None, rval_storage_type=None):
		super().__init__(type, arg_storage_type, bound_name, rval_storage_type)

	def get_type_glue(self, gen, module_name):
		out = '''bool check_%s(PyObject *o) {
	if (PyLong_Check(o))
		return true;
	if (wrapped_Object *w = cast_to_wrapped_Object_safe(o))
		return _type_tag_can_cast(w->type_tag, %s);
	return false;
}\n''' % (self.bound_name, self.type_tag)

		out += '''void to_c_%s(PyObject *o, void *obj) {
	if (PyLong_Check(o)) {
		*(void **)obj = PyLong_AsVoidPtr(o);
	} else if (wrapped_Object *w = cast_to_wrapped_Object_unsafe(o)) {
		*(void **)obj = _type_tag_cast(w->obj, w->type_tag, %s);
	}
}\n''' % (self.bound_name, self.type_tag)

		out += '''PyObject *from_c_%s(void *obj, OwnershipPolicy) {
	return PyLong_FromVoidPtr(*(void **)obj);
}\n''' % self.bound_name

		return out


#
class CPythonGenerator(gen.FABGen):
	default_class_converter = PythonClassTypeDefaultConverter
	default_ptr_converter = PythonPtrTypeDefaultConverter

	def __init__(self):
		super().__init__()

		self.api_prefix = 'cpython'
		self.check_self_type_in_ops = True

	def get_language(self):
		return "CPython"

	def output_includes(self):
		super().output_includes()

		self._source += '''#define Py_LIMITED_API // ensure a single build for Python 3.x (with x>2)
#include "Python.h"
\n'''

	def start(self, module_name):
		super().start(module_name)

		self._source += '''\
struct type_tag_info {
	const char *type_tag;
	const char *c_type;

	bool (*check)(PyObject *o);
	void (*to_c)(PyObject *o, void *obj);
	PyObject *(*from_c)(void *obj, OwnershipPolicy);
};
\n'''

		self._source += 'static type_tag_info *get_type_tag_info(const char *type_tag);\n\n'

		self._source += '''\
typedef struct {
	PyObject_HEAD;

	uint32_t magic_u32; // wrapped_Object marker
	const char *type_tag; // wrapped pointer type tag

	void *obj;
	char inline_obj[16]; // storage for inline objects

	void (*on_delete)(void *);
} wrapped_Object;

static void init_wrapped_Object(wrapped_Object *o, const char *type_tag, void *obj) {
	o->magic_u32 = 0x46414221;
	o->type_tag = type_tag;

	o->obj = obj;

	o->on_delete = NULL;
}

static wrapped_Object *cast_to_wrapped_Object_safe(PyObject *o) {
	wrapped_Object *w = (wrapped_Object *)o;
	if (w->magic_u32 != 0x46414221)
		return NULL;
	return w;
}

static wrapped_Object *cast_to_wrapped_Object_unsafe(PyObject *o) { return (wrapped_Object *)o; }

static void wrapped_Object_tp_dealloc(PyObject *self) {
	wrapped_Object *w = (wrapped_Object *)self;

	if (w->on_delete)
		w->on_delete(w->obj);

	PyObject_Del(self); // tp_free should be used but PyType_GetSlot is 3.4+
}
\n'''

		self._source += '''\
static inline bool CheckArgsTuple(PyObject *args) {
	if (!PyTuple_Check(args)) {
		PyErr_SetString(PyExc_RuntimeError, "invalid arguments object (expected a tuple)");
		return false;
	}
	return true;
}
\n'''

	#
	def set_error(self, type, reason):
		return 'PyErr_SetString(PyExc_RuntimeError, "%s");\n' % reason

	#
	def get_self(self, ctx):
		if ctx in ['arithmetic_op', 'inplace_arithmetic_op', 'comparison_op']:
			return 'o1'
		return 'self'

	def get_arg(self, i, ctx):
		if ctx in ['arithmetic_op', 'inplace_arithmetic_op', 'comparison_op']:
			return 'o%d' % (i+2)
		elif ctx == 'setter':
			return 'val'
		return 'arg_pyobj[%d]' % i

	def open_proxy(self, name, max_arg_count, ctx):
		out = ''

		if ctx == 'getter':
			out += 'static PyObject *%s(PyObject *self, void *closure) {\n' % name
		elif ctx == 'setter':
			out += 'static int %s(PyObject *self, PyObject *val, void *closure) {\n' % name
		elif ctx in ['arithmetic_op', 'inplace_arithmetic_op', 'comparison_op']:
			out += 'static PyObject *%s(PyObject *o1, PyObject *o2) {\n' % name
		else:
			out += 'static PyObject *%s(PyObject *self, PyObject *args) {\n' % name
			out += '''	if (!CheckArgsTuple(args))
		return NULL;
	int arg_count = PyTuple_Size(args);
\n'''

			if max_arg_count > 0:
				out += '\
	PyObject *arg_pyobj[%d];\n\
	for (int _i = 0; _i < arg_count && _i < %d; ++_i)\n\
		arg_pyobj[_i] = PyTuple_GetItem(args, _i);\n\
\n' % (max_arg_count, max_arg_count)

		return out

	def close_proxy(self, ctx):
		if ctx == 'setter':
			return '	return -1;\n}\n'
		elif ctx == 'getter':
			return '}\n'
		return '	return NULL;\n}\n'

	def proxy_call_error(self, msg, ctx):
		out = self.set_error('runtime', msg)

		if ctx == 'setter':
			out += 'return -1;\n'
		else:
			out += 'return NULL;\n'

		return out

	# function call return values
	def return_void_from_c(self):
		return 'return 0;'

	def declare_rval(self, out_var):
		return 'PyObject *%s;\n' % out_var

	def rval_from_c_ptr(self, conv, out_var, expr, ownership):
		return conv.from_c_call(out_var, expr, ownership)

	def commit_rvals(self, rvals, ctx='default'):
		out = ''

		if ctx == 'setter':
			out += 'return 0;\n'
		elif ctx == 'inplace_arithmetic_op':
			self_var = self.get_self(ctx)
			out += 'Py_INCREF(%s);\nreturn %s;\n' % (self_var, self_var)
		else:
			rval_count = len(rvals)
			rvals = [rval + '_out' for rval in rvals]

			if rval_count == 0:
				out += 'Py_INCREF(Py_None);\nreturn Py_None;\n'
			elif rval_count == 1:
				out += 'return %s;\n' % rvals[0]
			else:
				out += 'return PyTuple_Pack(%d, %s);\n' % (rval_count, ', '.join(rvals))

		return out

	#
	def output_module_functions_table(self):
		table_name = '%s_Methods' % self._name
		self._source += "static PyMethodDef %s[] = {\n" % table_name

		rows = []
		for f in self._bound_functions:
			rows.append('	{"%s", %s, METH_VARARGS, "TODO doc"}' % (f['bound_name'], f['proxy_name']))
		rows.append('	{NULL, NULL, 0, NULL} /* Sentinel */')

		self._source += ',\n'.join(rows) + '\n'
		self._source += "};\n\n"
		return table_name

	def output_module_free(self):
		self._source += 'void PyFree_%s(void *) {\n' % self._name
		self._source += '	// custom free code\n'
		self._source += self._custom_free_code
		self._source += '}\n\n'

	def output_module_definition(self, methods_table):
		self.output_module_free()

		def_name = '%s_module' % self._name
		self._source += 'static struct PyModuleDef %s = {\n' % def_name
		self._source += '	PyModuleDef_HEAD_INIT,\n'
		self._source += '	"%s", /* name of module */\n' % self._name
		self._source += '	"TODO doc", /* module documentation, may be NULL */\n'
		self._source += '	-1, /* size of per-interpreter state of the module, or -1 if the module keeps state in global variables. */\n'
		self._source += '	%s,\n' % methods_table
		self._source += '	NULL, /* m_slots */\n'
		self._source += '	NULL, /* m_traverse */\n'
		self._source += '	NULL, /* m_clear */\n'
		self._source += '	&PyFree_%s /* m_free */\n' % self._name
		self._source += '};\n\n'

		return def_name

	def output_module_init_function(self, module_def):
		self._source += 'PyMODINIT_FUNC PyInit_%s(void) {\n' % self._name
		self._source += '	// custom initialization code\n'
		self._source += self._custom_init_code

		self._source += '''
	PyObject *m = PyModule_Create(&%s);
	if (m == NULL)
		return NULL;

''' % module_def

		# module constants
		if len(self._enums) > 0:
			for name, enum in self._enums.items():
				self._source += '	// enumeration %s\n' % name
				for name, value in enum.items():
					self._source += '	PyModule_AddIntConstant(m, "%s", (long)%s);\n' % (name, value)
			self._source += '\n'

		# finalize bound types
		if len(self._bound_types) > 0:
			self._source += '	// custom types finalization\n'
			for conv in self._bound_types:
				if not conv.nobind:
					self._source += conv.finalize_type()

		self._source += '''\
	return m;
}
\n'''

	def finalize(self):
		self._source += '// Module definitions starts here.\n\n'

		# self.output_summary()

		methods_table = self.output_module_functions_table()
		module_def = self.output_module_definition(methods_table)

		# typetag info structure
		self._source += 'static type_tag_info type_tag_infos[] = {\n'
		entries = []
		for type in self._bound_types:
			entries.append('	{%s, "%s", check_%s, to_c_%s, from_c_%s}' % (type.type_tag, str(type.ctype), type.bound_name, type.bound_name, type.bound_name))
		entries.append('	{nullptr, nullptr, nullptr, nullptr, nullptr}')
		self._source += ',\n'.join(entries) + '\n'
		self._source += '};\n\n'

		self._source += '''
static type_tag_info *get_type_tag_info(const char *type_tag) {
	for (type_tag_info *info = type_tag_infos; info->type_tag != nullptr; ++info)
		if (info->type_tag == type_tag)
			return info;
	return NULL;
}\n\n'''

		# generic finalization
		super().finalize()

		self.output_module_init_function(module_def)
