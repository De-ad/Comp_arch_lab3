from __future__ import annotations

import json
from enum import Enum


class OpcodeParamType(str, Enum):
	CONST = "const"
	ADDR = "addr"
	UNDEFINED = "undefined"
	ADDR_REL = "addr_rel"


class OpcodeParam:
	def __init__(self, param_type: OpcodeParamType, value: any):
		self.param_type = param_type
		self.value = value

	def __str__(self):
		return f"({self.param_type}, {self.value})"


class OpcodeType(str, Enum):
	NOP = "nop"
	ADD = "add"
	MOD = "mod"
	SWAP = "swap"
	DUP = "dup"
	EQ = "eq"
	DI = "di"
	EI = "ei"
	OMIT = "omit"
	READ = "read"
	STORE = "store"
	LOAD = "load"
	PUSH = "push"
	JMP = "jmp"
	ZJMP = "zjmp"
	CALL = "call"
	RET = "ret"
	HALT = "halt"

	def __str__(self):
		return str(self.value)


class Opcode:
	def __init__(self, opcode_type: OpcodeType, params: list[OpcodeParam]):
		self.opcode_type = opcode_type
		self.params = params


class TermType(Enum):
	(
		DI,
		EI,
		DUP,
		ADD,
		OMIT,
		SWAP,
		DROP,
		OVER,
		EQ,
		READ,
		VARIABLE,
		ALLOT,
		STORE,
		LOAD,
		IF,
		ELSE,
		THEN,
		PRINT,
		DEF,
		RET,
		DEF_INTR,
		WHILE,
		ENDWHILE,
		CALL,
		STRING,
		ENTRYPOINT,
	) = range(26)


term_opcode_mapping = {
	"di": TermType.DI,
	"ei": TermType.EI,
	"dup": TermType.DUP,
	"+": TermType.ADD,
	"omit": TermType.OMIT,
	"read": TermType.READ,
	"=": TermType.EQ,
	"variable": TermType.VARIABLE,
	"allot": TermType.ALLOT,
	"!": TermType.STORE,
	"@": TermType.LOAD,
	"if": TermType.IF,
	"else": TermType.ELSE,
	"then": TermType.THEN,
	":": TermType.DEF,
	";": TermType.RET,
	"interrupt": TermType.DEF_INTR,
	"while": TermType.WHILE,
	"endwhile": TermType.ENDWHILE,
}


def write_code(filename: str, code: list[dict]):
	with open(filename, "w", encoding="utf-8") as file:
		buf = []
		for instr in code:
			buf.append(json.dumps(instr))
		file.write("[" + ",\n ".join(buf) + "]")


def write_memory(filename: str, memory: list):
	with open(filename, "w", encoding="utf-8") as file:
		file.write("[" + ", ".join(list(map(str, memory))) + "]")


def read_code(source_path: str) -> list:
	with open(source_path, encoding="utf-8") as file:
		return json.loads(file.read())
