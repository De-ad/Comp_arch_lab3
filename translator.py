from __future__ import annotations

import shlex
import sys

from codegen_utils import Terminal, codegen_opcodes
from isa import Opcode, OpcodeParamType, OpcodeType, TermType, term_opcode_mapping, write_code, write_memory

variables = {}
functions = {}
current_address = 0
data_memory = [0] * 1024
string_current_address = 0


def get_term(word: str) -> Terminal | None:
	if word not in term_opcode_mapping:
		return None

	return term_opcode_mapping[word]


def create_bindings(terms: list[Terminal]):
	for term in terms:
		if term.term_type is None and not term.converted:
			if term.word in variables:
				term.word = str(variables[term.word])

	for term in terms:
		if term.term_type is None and not term.converted:
			if term.word in functions.keys():
				term.operand = functions[term.word]
				term.term_type = TermType.CALL
				term.word = "call"


def fetch_ret_addresses(terms: list[Terminal]):
	global functions
	func_indexes = []

	for term_index, term in enumerate(terms):
		if term.term_type is TermType.DEF or term.term_type is TermType.DEF_INTR:
			func_indexes.append(term.word_number)
			func_name = terms[term_index + 1].word
			functions[func_name] = term.word_number + 1
			terms[term_index + 1].converted = True

		if term.term_type == TermType.RET:
			assert len(func_indexes) >= 1
			function_term = terms[func_indexes.pop()]
			function_term.operand = term.word_number + 1

	assert len(func_indexes) == 0


def stream_to_terms(source_code: str) -> list[Terminal]:
	# split and parse to terminals
	code_words = shlex.split(source_code.replace("\n", " "), posix=True)
	code_words = list(filter(lambda x: len(x) > 0, code_words))
	terms = [Terminal(0, TermType.ENTRYPOINT, "")]

	for word_number, word in enumerate(code_words):
		# from mapping
		term_type = get_term(word)

		# case of string literal
		if word[:2] == ". ":
			word = f'."{word[2:]}"'
			term_type = TermType.STRING

		terms.append(Terminal(word_number + 1, term_type, word))

	return terms


def validate_loops(terms: list[Terminal], begin: TermType, end: TermType, msg: str):
	nested = []

	for term in terms:
		if term.term_type is begin:
			nested.append(term.word_number)
		if term.term_type == end:
			assert len(nested) > 0, msg
			term.operand = nested.pop()

	# should have gone all down to zero
	assert len(nested) == 0, msg


def fetch_opcode_addresses(term_opcodes: list[list[Opcode]]) -> list[Opcode]:
	result_opcodes = []
	pref_sum = [0]

	for term_num, opcodes in enumerate(term_opcodes):
		term_opcode_cnt = len(opcodes)
		pref_sum.append(pref_sum[term_num] + term_opcode_cnt)

	for term_opcode in list(filter(lambda x: x is not None, term_opcodes)):
		for opcode in term_opcode:
			for param_num, param in enumerate(opcode.params):
				if param.param_type is OpcodeParamType.ADDR:
					opcode.params[param_num].value = pref_sum[param.value]
					opcode.params[param_num].param_type = OpcodeParamType.CONST
				if param.param_type is OpcodeParamType.ADDR_REL:
					opcode.params[param_num].value = len(result_opcodes) + opcode.params[param_num].value
					opcode.params[param_num].param_type = OpcodeParamType.CONST

			result_opcodes.append(opcode)

	return result_opcodes


def fetch_vars(terms: list[Terminal]):
	global current_address

	for term_index, term in enumerate(terms):
		if term.term_type is TermType.VARIABLE:
			variables[terms[term_index + 1].word] = current_address
			current_address += 1
			terms[term_index + 1].converted = True
			if term_index + 3 < len(terms) and terms[term_index + 3].term_type is TermType.ALLOT:
				fetch_allocates(terms, term_index + 3)


def fetch_allocates(terms: list[Terminal], term_index: int):
	global current_address
	assert term_index + 3 < len(terms)

	term = terms[term_index]

	if term.term_type is TermType.ALLOT:
		assert term_index - 3 >= 0
		terms[term_index - 1].converted = True
		allot_size = int(terms[term_index - 1].word)
		current_address += allot_size


def fetch_if_statement(terms: list[Terminal]):
	nested_ifs = []

	for term in terms:
		if term.term_type is TermType.IF:
			nested_ifs.append(term)
		elif term.term_type is TermType.ELSE:
			nested_ifs.append(term)
		elif term.term_type is TermType.THEN:
			last_if = nested_ifs.pop()

			if last_if.term_type is TermType.ELSE:
				last_else = last_if
				last_if = nested_ifs.pop()
				last_else.operand = term.word_number + 1
				last_if.operand = last_else.word_number + 1
			else:
				last_if.operand = term.word_number + 1


def handle_interruption_vectors(terms: list[Terminal]) -> list[Terminal]:
	is_interrupt = False
	interrupt_ret = 1
	terms_interrupt_proc = []
	terms_not_interrupt_proc = []

	for term in terms[1:]:
		if term.term_type is TermType.DEF_INTR:
			is_interrupt = True
		if term.term_type is TermType.RET:
			if is_interrupt:
				terms_interrupt_proc.append(term)
				interrupt_ret = len(terms_interrupt_proc) + 1
			else:
				terms_not_interrupt_proc.append(term)
			is_interrupt = False

		if is_interrupt:
			terms_interrupt_proc.append(term)
		elif not is_interrupt and term.term_type is not TermType.RET:
			terms_not_interrupt_proc.append(term)

	# add jump to code
	terms[0].operand = interrupt_ret

	return [*[terms[0]], *terms_interrupt_proc, *terms_not_interrupt_proc]


def terms_to_opcodes(terms: list[Terminal]) -> list[Opcode]:
	global current_address
	terms = handle_interruption_vectors(terms)
	opcodes = []
	for i in range(len(terms)):
		opcode, current_address = codegen_opcodes(terms[i], string_current_address, data_memory)
		opcodes.append(opcode)
	opcodes = fetch_opcode_addresses(opcodes)
	return [*opcodes, Opcode(OpcodeType.HALT, [])]


def validate_terms(terms: list[Terminal]):
	validate_loops(terms, TermType.WHILE, TermType.ENDWHILE, "Didnt close begin")

	fetch_ret_addresses(terms)
	fetch_vars(terms)
	create_bindings(terms)
	fetch_if_statement(terms)


def translate(source_code: str) -> (list[dict], list):
	global data_memory, current_address
	current_address = 0
	data_memory = [0] * 1024
	terms = stream_to_terms(source_code)
	validate_terms(terms)
	opcodes = terms_to_opcodes(terms)
	commands = []
	for index, opcode in enumerate(opcodes):
		command = {
			"index": index,
			"command": opcode.opcode_type.name,
		}
		if len(opcode.params):
			if isinstance(opcode.params[0].value, str) and opcode.params[0].value.isdigit():
				command["arg"] = int(opcode.params[0].value)
			else:
				command["arg"] = opcode.params[0].value
		commands.append(command)
	return commands, data_memory


def main(source_file: str, target_file: str, mem_out: str) -> None:
	global data_memory
	with open(source_file, encoding="utf-8") as f:
		source_code = f.read()
	code, data_memory = translate(source_code)
	write_code(target_file, code)
	write_memory(mem_out, data_memory)


if __name__ == "__main__":
	assert len(sys.argv) == 4, "Wrong arguments: translator.py <input_file> <target_file> <mem_out>"
	_, source, target, mem_out = sys.argv
	main(source, target, mem_out)
