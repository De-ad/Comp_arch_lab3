import pytest
from machine import run
from translator import translate


@pytest.mark.golden_test("./golden/*.yaml")
def test_golden_emulator(golden) -> None:
	code, data_memory = translate(str(golden["code"]))
	assert code == golden.out["instructions"]
	assert data_memory == golden.out["data_memory"]
	input_tokens = eval(str(golden["input"]))

	output, ticks, journal = run(
		code,
		data_memory,
		limit=999,
		input_tokens=input_tokens,
	)

	journal.insert(0, f"Output buffer: {output}")
	journal.insert(0, f"Number of ticks: {ticks - 1}")

	assert journal == golden.out["journal"]
