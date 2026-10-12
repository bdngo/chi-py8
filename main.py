import time
import tkinter as tk
from dataclasses import dataclass
from enum import Enum

import keyboard

MEM_SIZE: int = 4086
REG_FILE_SIZE: int = 16
FONT_TABLE = bytes([
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
])
DISPLAY_WIDTH: int = 64
DISPLAY_HEIGHT: int = 32
CLK_FREQ_HZ: int = 700
SCALE: int = 12
ON, OFF = "#FFFFFF", "#000000"


@dataclass(frozen=True)
class ClearScreen:
    pass


@dataclass(frozen=True)
class Jump:
    immediate: int


@dataclass(frozen=True)
class SetRegister:
    x: int
    immediate: int


@dataclass(frozen=True)
class AddImmediate:
    x: int
    immediate: int


@dataclass(frozen=True)
class SetIndexRegister:
    immediate: int


@dataclass(frozen=True)
class Display:
    x: int
    y: int
    n: int


Instruction = ClearScreen | Jump | SetRegister | AddImmediate | SetIndexRegister | Display


def initialize_memory() -> bytearray:
    memory = bytearray(MEM_SIZE)
    memory[0x050:0x0A0] = FONT_TABLE
    return memory

def initialize_display() -> list[list[bool]]:
    return [[False] * DISPLAY_WIDTH for _ in range(DISPLAY_HEIGHT)]


class Chip8Emulator:
    def __init__(self):
        self.memory = initialize_memory()
        self.pc = 0x0  # 16-bit
        self.index_register = 0  # 16-bit
        self.stack: list[int] = []
        self.delay_timer = 0  # 8-bit
        self.sound_timer = 0  # 8-bit
        self.reg_file = bytearray(REG_FILE_SIZE)
        self.display = initialize_display()

    @staticmethod
    def decode_instr(instr: bytes) -> Instruction | None:
        msb, lsb = instr[0], instr[1]
        nibbles = (
            msb >> 4,
            msb & 0x0F,
            lsb >> 4,
            lsb & 0x0F,
        )

        x = nibbles[1]
        y = nibbles[2]
        n = nibbles[3]
        nn = lsb
        nnn = (x << 8) | nn

        match nibbles[0]:
            case 0x0:
                return ClearScreen()
            case 0x1:
                return Jump(nnn)
            case 0x6:
                return SetRegister(x, nn)
            case 0x7:
                return AddImmediate(x, nn)
            case 0xA:
                return SetIndexRegister(nnn)
            case 0xD:
                return Display(x, y, n)
            case _:
                return None


    def execute_instr(self, instr: Instruction) -> None:
        match instr:
            case ClearScreen():
                self.display = initialize_display()
            case Jump(nnn):
                self.pc = nnn
            case SetRegister(x, nn):
                self.reg_file[x] = nn
            case AddImmediate(x, nn):
                self.reg_file[x] = (self.reg_file[x] + nn) % (1 << 8)
            case SetIndexRegister(nnn):
                self.index_register = nnn
            case Display(x, y, n):
                self.draw_display(self.reg_file[x], self.reg_file[y], n)

    def draw_display(self, vx: int, vy: int, n: int) -> None:
        x0 = vx % DISPLAY_WIDTH
        y = vy % DISPLAY_HEIGHT
        self.reg_file[0xF] = 0x00

        for r in range(n):
            sprite = self.memory[self.index_register + r]
            x = x0
            for i in range(8):
                curr_pixel = self.display[y][x]
                bit = (sprite >> (7 - i)) & 1
                if bit == 1 and curr_pixel:
                    self.display[y][x] = False
                    self.reg_file[0xF] = 0x01
                elif bit == 1 and not curr_pixel:
                    self.display[y][x] = True
                x += 1
                if x >= DISPLAY_WIDTH:
                    break
            y += 1
            if y >= DISPLAY_HEIGHT:
                break

class TkDisplay:
    def __init__(self, root: tk.Tk):
        self.canvas = tk.Canvas(
            root, width=DISPLAY_WIDTH * SCALE, height=DISPLAY_HEIGHT * SCALE,
            bg=OFF, highlightthickness=0,
        )
        self.canvas.pack()
        # Create all rectangles once; later only recolor them
        self.cells = [
            [
                self.canvas.create_rectangle(
                    x * SCALE, y * SCALE, (x + 1) * SCALE, (y + 1) * SCALE,
                    fill=OFF, outline="",
                )
                for x in range(DISPLAY_WIDTH)
            ]
            for y in range(DISPLAY_HEIGHT)
        ]
        self.prev = [[0] * DISPLAY_WIDTH for _ in range(DISPLAY_HEIGHT)]

    def draw(self, matrix):
        for y, row in enumerate(matrix):
            for x, v in enumerate(row):
                if v != self.prev[y][x]: # only touch changed cells
                    self.canvas.itemconfig(self.cells[y][x], fill=ON if v else OFF)
                    self.prev[y][x] = v


def main():
    # print("Hello from chi-py8!")
    emulator = Chip8Emulator()
    
    with open("IBM Logo.ch8", "rb") as f:
        program = f.read()
        emulator.memory[0x200:0x200+len(program)] = program

    root = tk.Tk()
    root.title("CHIP-8 Emulator")
    display = TkDisplay(root)

    def tick():
        instr = emulator.memory[emulator.pc:emulator.pc+2]
        emulator.pc = (emulator.pc + 2) % (1 << 16)
        decoded_instr = emulator.decode_instr(instr)
        emulator.execute_instr(decoded_instr)

        display.draw(emulator.display)
        root.after(1, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()

