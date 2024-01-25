from __future__ import annotations

import typing
from enum import Enum

from isa import OpcodeType


class ALUOpcode(str, Enum):
	INC_A = "inc_a"
	INC_B = "inc_b"
	DEC_A = "dec_a"
	DEC_B = "dec_b"
	ADD = "add"
	EQ = "eq"

	def __str__(self) -> str:
		return str(self.value)


class ALU:
	alu_operations: typing.ClassVar[list[ALUOpcode]] = [
		ALUOpcode.INC_A,
		ALUOpcode.INC_B,
		ALUOpcode.DEC_A,
		ALUOpcode.DEC_B,
		ALUOpcode.ADD,
		ALUOpcode.EQ,
	]

	def __init__(self):
		self.result = 0
		self.src_a = None
		self.src_b = None
		self.operation = None

	def calc(self) -> None:
		match self.operation:
			case ALUOpcode.INC_A:
				self.result = self.src_a + 1
			case ALUOpcode.INC_B:
				self.result = self.src_b + 1
			case ALUOpcode.DEC_A:
				self.result = self.src_a - 1
			case ALUOpcode.DEC_B:
				self.result = self.src_b - 1
			case ALUOpcode.ADD:
				self.result = self.src_a + self.src_b
			case ALUOpcode.EQ:
				self.result = int(self.src_a == self.src_b)

	def set_details(self, src_a, src_b, operation: ALUOpcode) -> None:
		self.src_a = src_a
		self.src_b = src_b
		self.operation = operation


def opcode_to_alu_opcode(opcode_type: OpcodeType):
	return {
		OpcodeType.ADD: ALUOpcode.ADD,
		OpcodeType.EQ: ALUOpcode.EQ,
	}.get(opcode_type)
