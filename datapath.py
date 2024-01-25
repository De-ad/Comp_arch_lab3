from enum import Enum

import pytest as pytest
from alu import ALU


class Selector(str, Enum):
	SP_INC = "increase sp"
	SP_DEC = "decrease sp"
	PC_INC = "increase pc"
	RSP_INC = "increase rsp"
	RSP_DEC = "decrease rsp"
	NEXT_TOP = "next -> top"
	NEXT_TEMP = "next -> temp"
	TEMP_NEXT = "temp-> next"
	TEMP_TOP = "temp -> top"
	TEMP_RETURN = "return to temp"
	TOP_TEMP = "top ->temp"
	TOP_NEXT = "top -> next"
	TOP_ALU = "top -> alu"
	TOP_MEM = "top -> mem"
	RET_STACK_PC = "push pc to rstack"
	NEXT_MEM = "next -> mem"
	TOP_IMMEDIATE = "top -> immediate"
	TOP_INPUT = "top -> input"
	PC_RET = "pc -> ret"
	PC_IMMEDIATE = "pc -> immediate"

	def __str__(self) -> str:
		return str(self.value)


# Constants
DATA_MEMORY_DEF_VALUE = 0
DATA_STACK_DEF_VALUE = 0
RETURN_STACK_DEF_VALUE = 0
TOP_INPUT_DEF_VALUE = 0
STACK_PTR_OFFSET = 4


class DataPath:
	def __init__(self, memory_size: int, memory: list, data_stack_size: int, return_stack_size: int):
		assert all(
			size > 0 for size in [memory_size, data_stack_size, return_stack_size]
		), "Sizes must be greater than zero"

		self.sp = STACK_PTR_OFFSET
		self.rsp = STACK_PTR_OFFSET
		self.pc = 0
		self.top = self.next = self.temp = DATA_STACK_DEF_VALUE

		self.alu = ALU()

		self.memory_size = memory_size
		self.data_stack_size = data_stack_size
		self.return_stack_size = return_stack_size

		self.memory = memory
		self.data_stack = [DATA_STACK_DEF_VALUE] * data_stack_size
		self.return_stack = [RETURN_STACK_DEF_VALUE] * return_stack_size

	def signal_alu_operation(self, operation) -> None:
		self.alu.set_details(self.top, self.next, operation)
		self.alu.calc()

	def signal_latch_sp(self, selector: Selector) -> None:
		self.sp += 1 if selector is Selector.SP_INC else -1

	def signal_latch_rsp(self, selector: Selector) -> None:
		self.rsp += 1 if selector is Selector.RSP_INC else -1

	def signal_latch_next(self, selector: Selector) -> None:
		if selector is Selector.NEXT_MEM:
			assert 0 <= self.sp < self.data_stack_size, "Address out of bounds"
			self.next = self.data_stack[self.sp]
		elif selector is Selector.NEXT_TOP:
			self.next = self.top
		elif selector is Selector.NEXT_TEMP:
			self.next = self.temp

	def signal_latch_temp(self, selector: Selector) -> None:
		if selector is Selector.TEMP_RETURN:
			assert self.rsp >= 0, "Address below 0"
			assert self.rsp < self.return_stack_size, "Return stack overflow"
			self.temp = self.return_stack[self.rsp]
		elif selector is Selector.TEMP_TOP:
			self.temp = self.top
		elif selector is Selector.TEMP_NEXT:
			self.temp = self.next

	def signal_latch_top(self, selector: Selector, immediate=0) -> None:
		match selector:
			case Selector.TOP_NEXT:
				self.top = self.next
			case Selector.TOP_ALU:
				self.top = self.alu.result
			case Selector.TOP_TEMP:
				self.top = self.temp
			case Selector.TOP_INPUT:
				self.top = TOP_INPUT_DEF_VALUE
			case Selector.TOP_MEM:
				assert 0 <= self.top < self.memory_size, "Address out of bounds"
				self.top = self.memory[self.top]
			case Selector.TOP_IMMEDIATE:
				self.top = immediate

	def signal_mem_write(self) -> None:
		assert 0 <= self.top < self.memory_size, "Address out of bounds"
		self.memory[self.top] = self.next

	def signal_data_wr(self) -> None:
		assert self.sp >= 0, "Address below 0"
		assert self.sp < self.data_stack_size, "Data stack overflow"
		self.data_stack[self.sp] = self.next

	def signal_ret_wr(self, selector: Selector) -> None:
		assert self.rsp >= 0, "Address below 0"
		assert self.rsp < self.return_stack_size, "Return stack overflow"
		if selector is Selector.RET_STACK_PC:
			self.return_stack[self.rsp] = self.pc
