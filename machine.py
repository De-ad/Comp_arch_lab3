from __future__ import annotations

import json
import logging
import sys
import typing
from functools import partial

from alu import opcode_to_alu_opcode
from datapath import DataPath, Selector
from isa import OpcodeType, read_code

logger = logging.getLogger("machine_logger")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

irq_request = "IRQ_R"
irq_on = "IRQ_ON"


class ControlUnit:
	out_buffer = ""
	journal = []
	IO = "h"

	already_fetched: list[bool] = []
	tokens: list[tuple] = []

	tick_number = 0
	instruction_number = 0

	def __init__(self, data_path: DataPath, program_memory_size: int, input_tokens: list[tuple]):
		self.data_path = data_path
		self.tokens = input_tokens
		self.already_fetched = [False for _ in input_tokens]
		self.program_memory_size = program_memory_size
		self.program_memory = [{"index": x, "command": 0, "arg": 0} for x in range(self.program_memory_size)]
		self.ps = {irq_request: False, irq_on: True}

	def tick(self, operation: typing.Callable) -> None:
		self.tick_number += 1
		operation()
		self.__print__()

	def fetch_single_command(self):
		self.instruction_number += 1
		self.decode_instruction()
		self.handle_irq()
		self.signal_latch_pc(Selector.PC_INC)

	def init_instructions(self, opcodes: list) -> None:
		for opcode in opcodes:
			mem_cell = int(opcode["index"])
			assert 0 <= mem_cell < self.program_memory_size, "Program index out of memory size"
			self.program_memory[mem_cell] = opcode

	def signal_latch_pc(self, selector: Selector, immediate=0) -> None:
		match selector:
			case Selector.PC_INC:
				self.data_path.pc += 1
			case Selector.PC_RET:
				self.data_path.pc = self.data_path.return_stack[self.data_path.rsp]
			case Selector.PC_IMMEDIATE:
				self.data_path.pc = immediate - 1

	def signal_latch_ps(self, intr_on: bool) -> None:
		self.ps[irq_on] = intr_on
		self.ps[irq_request] = self.handle_irq()

	def handle_irq(self) -> bool:
		if self.ps[irq_on]:
			for index, interrupt in enumerate(self.tokens):
				if not self.already_fetched[index] and interrupt[0] <= self.tick_number:
					self.ps[irq_request] = True
					self.ps[irq_on] = False
					self.already_fetched[index] = True
					self.IO = interrupt[1]
					self.tick(partial(self.data_path.signal_ret_wr, Selector.RET_STACK_PC))
					self.tick(partial(self.signal_latch_pc, Selector.PC_IMMEDIATE, 1))
					self.tick(partial(self.data_path.signal_latch_rsp, Selector.RSP_INC))
					break
		return False

	def handle_push(self, memory_cell):
		self.tick(partial(self.data_path.signal_data_wr))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_INC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_TOP))
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_IMMEDIATE, memory_cell["arg"]))

	def handle_drop(self):
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))

	def handle_omit(self):
		self.out_buffer += chr(self.data_path.next)
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))

	def handle_read(self):
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
		self.tick(partial(self.data_path.signal_data_wr))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_INC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_TOP))
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_IMMEDIATE, ord(self.IO)))

	def handle_rpop(self):
		self.tick(partial(self.data_path.signal_latch_rsp, Selector.RSP_DEC))
		self.tick(partial(self.data_path.signal_latch_temp, Selector.TEMP_RETURN))
		self.tick(partial(self.data_path.signal_data_wr))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_TOP))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_INC))
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_TEMP))

	def handle_store(self):
		self.tick(partial(self.data_path.signal_mem_write))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
		self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))

	def handle_swap(self):
		self.tick(partial(self.data_path.signal_latch_temp, Selector.TEMP_TOP))
		self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
		self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_TEMP))

	def decode_instruction(self) -> None:
		memory_cell = self.program_memory[self.data_path.pc]
		command = memory_cell["command"].lower()
		arithmetic_operation = opcode_to_alu_opcode(command)

		if arithmetic_operation is None:
			self.tick(partial(self.data_path.signal_alu_operation, arithmetic_operation))
			self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_ALU))
			self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
			self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))
		else:
			match command:
				case OpcodeType.PUSH:
					self.handle_push(memory_cell)
				case OpcodeType.OMIT:
					self.handle_omit()
				case OpcodeType.READ:
					self.handle_read()
				case OpcodeType.SWAP:
					self.handle_swap()
				case OpcodeType.DUP:
					self.tick(partial(self.data_path.signal_data_wr))
					self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_TOP))
					self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_INC))
				case OpcodeType.LOAD:
					self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_MEM))
				case OpcodeType.STORE:
					self.handle_store()
				case OpcodeType.ZJMP:
					match self.data_path.top:
						case 0:
							self.tick(partial(self.signal_latch_pc, Selector.PC_IMMEDIATE, memory_cell["arg"]))
							self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
							self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
							self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))
						case _:
							self.tick(partial(self.data_path.signal_latch_top, Selector.TOP_NEXT))
							self.tick(partial(self.data_path.signal_latch_sp, Selector.SP_DEC))
							self.tick(partial(self.data_path.signal_latch_next, Selector.NEXT_MEM))
				case OpcodeType.JMP:
					self.tick(partial(self.signal_latch_pc, Selector.PC_IMMEDIATE, memory_cell["arg"]))
				case OpcodeType.CALL:
					self.tick(partial(self.data_path.signal_ret_wr, Selector.RET_STACK_PC))
					self.tick(partial(self.data_path.signal_latch_rsp, Selector.RSP_INC))
					self.tick(partial(self.signal_latch_pc, Selector.PC_IMMEDIATE, memory_cell["arg"]))
				case OpcodeType.DI:
					self.tick(partial(self.signal_latch_ps, False))
				case OpcodeType.EI:
					self.tick(partial(self.signal_latch_ps, True))
				case OpcodeType.RET:
					self.tick(partial(self.data_path.signal_latch_rsp, Selector.RSP_DEC))
					self.tick(partial(self.signal_latch_pc, Selector.PC_RET))
				case OpcodeType.HALT:
					print("end")
					raise StopIteration

	def __print__(self) -> None:
		tos_memory = self.data_path.data_stack[self.data_path.sp - 1 : self.data_path.sp - 2 : -1]
		tos = [self.data_path.top, self.data_path.next, *tos_memory]
		ret_tos = self.data_path.return_stack[self.data_path.rsp - 1 : self.data_path.rsp - 4 : -1]
		state_repr = (
			"TICK: {:4} | PC: {:4} | SP: {:3} | RSP: {:3} | IRQ_R {:2} | IRQ_ON: {:3} | "
			"S_HEAD : {} | RS_HEAD : {} | DATA_HEAD {:3}"
		).format(
			self.tick_number,
			self.data_path.pc,
			self.data_path.sp,
			self.data_path.rsp,
			self.ps[irq_request],
			self.ps[irq_on],
			str(tos),
			str(ret_tos),
			self.data_path.memory[self.data_path.top] if self.data_path.top < self.data_path.memory_size else "?",
		)
		self.journal.append(state_repr)
		logger.info(state_repr)


def run(code: list, memory: list, limit: int, input_tokens: list[tuple]):
	mem_limit = 1024
	data_path = DataPath(mem_limit, memory, mem_limit, mem_limit)
	control_unit = ControlUnit(data_path, mem_limit, input_tokens)

	control_unit.init_instructions(code)
	control_unit.journal = []

	# main cycle
	while control_unit.instruction_number < limit:
		try:
			control_unit.fetch_single_command()
		except StopIteration:
			break

	return [control_unit.out_buffer, control_unit.tick_number, control_unit.journal]


def emulate(instructions: str, memory_path: str, tokens: str | None):
	input_tokens = []
	if tokens is not None:
		with open(tokens, encoding="utf-8") as file:
			input_text = file.read()
			input_tokens = eval(input_text)
	code = read_code(instructions)
	memory = read_code(memory_path)
	output, ticks, journal = run(
		code,
		memory,
		limit=1000,
		input_tokens=input_tokens,
	)
	journal.insert(0, f"Output buffer: {output}")
	journal.insert(0, f"Number of ticks: {ticks - 1}")

	return journal


def main(code_path: str, memory_path: str, token_path: str | None) -> None:
	journal = emulate(code_path, memory_path, token_path)
	with open("ress", "w", encoding="utf-8") as file:
		file.write(json.dumps(journal))


if __name__ == "__main__":
	assert 3 <= len(sys.argv) <= 4, "Wrong arguments: machine.py <code_file> <memory_file> [<input_file>]"
	if len(sys.argv) == 4:
		_, code_file, machine_mem, input_file = sys.argv
	else:
		_, code_file, machine_mem = sys.argv
		input_file = None
	main(code_file, machine_mem, input_file)
