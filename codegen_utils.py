from __future__ import annotations

from isa import Opcode, OpcodeParam, OpcodeParamType, OpcodeType, TermType


class Terminal:
	def __init__(self, word_number: int, term_type: TermType | None, word: str):
		self.converted = False
		self.operand = None
		self.word_number = word_number
		self.term_type = term_type
		self.word = word


def codegen_print(term: Terminal, string_current_address, data_memory) -> (list[Opcode], int):
	if term.converted:
		opcodes = []
	elif term.term_type is not TermType.STRING:
		opcodes = [Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, term.word)])]
	else:
		opcodes = []
		start_string = string_current_address
		content = term.word[2:-1]
		for i in range(len(content)):
			data_memory[string_current_address] = ord(content[i])
			string_current_address += 1
		data_memory[string_current_address] = 0
		string_current_address += 1

		opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, start_string)]))
		opcodes.append(Opcode(OpcodeType.DUP, []))
		opcodes.append(Opcode(OpcodeType.LOAD, []))
		opcodes.append(Opcode(OpcodeType.DUP, []))
		opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, 0)]))
		opcodes.append(Opcode(OpcodeType.OMIT, []))
		opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, 0)]))
		opcodes.append(Opcode(OpcodeType.EQ, []))
		opcodes.append(Opcode(OpcodeType.SWAP, []))
		opcodes.append(Opcode(OpcodeType.PUSH, [OpcodeParam(OpcodeParamType.CONST, 1)]))
		opcodes.append(Opcode(OpcodeType.ADD, []))
		opcodes.append(Opcode(OpcodeType.SWAP, []))
		opcodes.append(Opcode(OpcodeType.ZJMP, [OpcodeParam(OpcodeParamType.ADDR_REL, -11)]))

		# begin dup @ dup omit = 0 until

	return opcodes, string_current_address


def codegen_opcodes(term: Terminal, string_current_address: int, data_memory: list) -> (list[Opcode], int):
	opcodes = {
		TermType.ADD: [Opcode(OpcodeType.ADD, [])],
		TermType.DI: [Opcode(OpcodeType.DI, [])],
		TermType.EI: [Opcode(OpcodeType.EI, [])],
		TermType.DUP: [Opcode(OpcodeType.DUP, [])],
		TermType.OMIT: [Opcode(OpcodeType.OMIT, [])],
		TermType.EQ: [Opcode(OpcodeType.EQ, [])],
		TermType.READ: [Opcode(OpcodeType.READ, [])],
		TermType.VARIABLE: [],
		TermType.ALLOT: [],
		TermType.STORE: [Opcode(OpcodeType.STORE, [])],
		TermType.LOAD: [Opcode(OpcodeType.LOAD, [])],
		TermType.IF: [Opcode(OpcodeType.ZJMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
		TermType.ELSE: [Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
		TermType.THEN: [],
		TermType.DEF: [Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
		TermType.RET: [Opcode(OpcodeType.RET, [])],
		TermType.DEF_INTR: [],
		TermType.WHILE: [],
		TermType.ENDWHILE: [Opcode(OpcodeType.ZJMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
		TermType.CALL: [Opcode(OpcodeType.CALL, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
		TermType.ENTRYPOINT: [Opcode(OpcodeType.JMP, [OpcodeParam(OpcodeParamType.UNDEFINED, None)])],
	}.get(term.term_type)

	if term.operand and opcodes is not None:
		for opcode in opcodes:
			for param_num, param in enumerate(opcode.params):
				if param.param_type is OpcodeParamType.UNDEFINED:
					opcode.params[param_num].param_type = OpcodeParamType.ADDR
					opcode.params[param_num].value = term.operand

	if opcodes is None:
		opcodes, string_current_address = codegen_print(term, string_current_address, data_memory)

	return opcodes, string_current_address
