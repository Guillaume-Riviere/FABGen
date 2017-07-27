class VectorSequenceFeature:
	def __init__(self, wrapped_conv):
		self.wrapped_conv = wrapped_conv

	def get_size(self, self_var, out_var):
		return '%s = %s->size();\n' % (out_var, self_var)

	def get_item(self, self_var, idx, out_var, error_var):
		out = 'if (size_t(%s) < %s->size())\n' % (idx, self_var)
		out += '	%s = (*%s)[%s];\n' % (out_var, self_var, idx)
		out += 'else\n'
		out += '	%s = true;\n' % error_var
		return out

	def set_item(self, self_var, idx, in_var, error_var):
		t_in_var = self.wrapped_conv.prepare_var_from_conv(in_var, self.wrapped_conv.ctype.get_ref())
		out = 'if (size_t(%s) < %s->size())\n' % (idx, self_var)
		out += '	(*%s)[%s] = %s;\n' % (self_var, idx, t_in_var)
		out += 'else\n'
		out += '	%s = true;\n' % error_var
		return out
