# MOS Technology 6502

## Infobox

- **Launched:** 1975; 51 years ago ( 1975 )
- **Common manufacturer:** MOS Technology, Rockwell, Synertek
- **Max. CPU clock rate:** 1 MHz to 3 MHz
- **Data width:** 8 bits
- **Address width:** 16 bits
- **Transistors:** 3,510, [ 1 ] 3,218 [ 2 ]
- **Package:** 40-pin DIP
- **Instruction set:** MOS 6502
- **Number of instructions:** 56 (55 originally)
- **Predecessors:** Motorola 6800 MOS 6501
- **Successors:** MOS 6510 WDC 65C02 WDC 65C816

The **MOS Technology 6502** is an [8-bit](/wiki/8-bit_computing) [microprocessor](/wiki/Microprocessor) that was designed by a small team led by [Chuck Peddle](/wiki/Chuck_Peddle) for [MOS Technology](/wiki/MOS_Technology) and was launched in September 1975. The design team had formerly worked at [Motorola](/wiki/Motorola) on the [Motorola 6800](/wiki/Motorola_6800) project; the 6502 is essentially a simplified, less expensive and faster version of that design using [depletion-load NMOS](/wiki/Depletion-load_NMOS_logic) technology that made using the microchip in computers much cheaper.

When it was introduced, the 6502 was the least expensive microprocessor on the market by a considerable margin. It initially sold for less than one-sixth the cost of competing designs from larger companies, such as the 6800 or [Intel 8080](/wiki/Intel_8080). Its introduction caused rapid decreases in pricing across the entire processor market. Along with the [Zilog Z80](/wiki/Zilog_Z80), it sparked a series of projects that resulted in the [home computer](/wiki/Home_computer) [revolution](/wiki/Microcomputer_revolution) of the early 1980s.

[Home video game consoles](/wiki/Home_video_game_console) and home computers of the 1970s through the early 1990s, such as the [Atari 2600](/wiki/Atari_2600), [Atari 8-bit computers](/wiki/Atari_8-bit_computers), [Apple II](/wiki/Apple_II), [Nintendo Entertainment System](/wiki/Nintendo_Entertainment_System), [Commodore 64](/wiki/Commodore_64), [Atari Lynx](/wiki/Atari_Lynx), [BBC Micro](/wiki/BBC_Micro) and others, use the 6502 or variations of the basic design. Soon after the 6502's introduction, MOS Technology was purchased outright by [Commodore International](/wiki/Commodore_International), who continued to sell the microprocessor and licenses to other manufacturers. In the early days of the 6502, it was [second-sourced](/wiki/Second_source) by [Rockwell](/wiki/Rockwell_International) and [Synertek](/wiki/Synertek), and later licensed to other companies.

In 1981, the [Western Design Center](/wiki/Western_Design_Center) started development of a [CMOS](/wiki/CMOS) version, the [65C02](/wiki/WDC_65C02). This continues to be widely used in [embedded systems](/wiki/Embedded_system), with estimated production volumes in the hundreds of millions.

## History and use

### Genesis at Motorola

Motorola 6800 demonstration board built by Chuck Peddle and John Buchanan in 1974

Motorola started the 6800 microprocessor project in 1971 with Tom Bennett as the main architect. Bennett hired [Chuck Peddle](/wiki/Chuck_Peddle) in 1973 to do architectural support work on the 6800 family products already in progress. Bennett already was at work on what became the 6800. "He hired me," Peddle says of Bennett, "to do the architectural support work for the product he'd already started." … Peddle says. "Motorola tried to kill it several times. Without Bennett, the 6800 would not have happened, and a lot of the industry would not have happened, either." Peddle contributed in many areas, including the design of the 6850 ACIA (serial interface).

Peddle would accompany Motorola salespeople on customer visits, and found that customers were put off by the high cost of the microprocessor chips. At the same time, these visits invariably resulted in the engineers he presented to producing lists of required instructions that were much smaller than "all these fancy instructions" that had been included in the 6800. Peddle and other team members started outlining the design of an improved feature, reduced-size microprocessor. At that time, Motorola's new semiconductor fabrication facility in [Austin, Texas](/wiki/Austin,_Texas), was having difficulty producing MOS chips, and mid-1974 was the beginning of a year-long recession in the semiconductor industry. Also, many of the [Mesa, Arizona](/wiki/Mesa,_Arizona) employees were displeased with the upcoming relocation to Austin.

Motorola's Semiconductor Products Division management showed no interest in Peddle's low-cost microprocessor proposal. Eventually, Peddle was given an official letter telling him to stop working on the system. Peddle responded to the order by informing Motorola that the letter represented an official declaration of "project abandonment", and as such, the intellectual property he had developed to that point was now his. The 6502 was designed by many of the same engineers that had designed the [Motorola 6800](/wiki/Motorola_6800) microprocessor family.

In a November 1975 interview, Motorola's Chairman, [Bob Galvin](/wiki/Bob_Galvin), ultimately agreed that Peddle's concept was a good one and that the division missed an opportunity, "We did not choose the right leaders in the Semiconductor Products division." The division was reorganized and the management replaced. The new group vice president John Welty said, "The semiconductor sales organization lost its sensitivity to customer needs and couldn't make speedy decisions."

### MOS Technology

A 1973 MOS Technology advertisement highlighting their custom integrated circuit capabilities

MOS Technology MCS6501, in white ceramic package, made in late August 1975

Peddle began looking outside Motorola for a source of funding for this new project. He initially approached [Mostek](/wiki/Mostek) CEO [L. J. Sevin](/wiki/L._J._Sevin), but was declined. Sevin later admitted this was because he was afraid Motorola would sue them.

While Peddle was visiting [Ford Motor Company](/wiki/Ford_Motor_Company) on one of his sales trips, Bob Johnson, later head of Ford's engine automation division, mentioned that their former colleague John Paivinen had moved to [General Instrument](/wiki/General_Instrument) and taught himself semiconductor design. Paivinen then formed [MOS Technology](/wiki/MOS_Technology) in [Valley Forge, Pennsylvania](/wiki/Valley_Forge,_Pennsylvania) in 1969 with two other executives from General Instrument, Mort Jaffe and Don McLaughlin. [Allen-Bradley](/wiki/Allen-Bradley), a supplier of electronic components and industrial controls, acquired a majority interest in 1970. The company designed and fabricated custom ICs for customers and had developed a line of calculator chips.

After the Mostek efforts fell through, Peddle approached Paivinen, who "immediately got it". On 19 August 1974, Chuck Peddle, Bill Mensch, Rod Orgill, Harry Bawcom, Ray Hirt, Terry Holdt, and Wil Mathys left Motorola to join MOS. Mike Janes joined later. Of the seventeen chip designers and layout people on the 6800 team, eight left. The goal of the team was to design and produce a low-cost microprocessor for embedded applications and to target as wide as possible a customer base. This would be possible only if the microprocessor was low cost, and the team set the price goal for volume purchases at $5. Mensch later stated the goal was not the processor price itself, but to create a set of chips that could sell at $20 to compete with the recently introduced [Intel 4040](/wiki/Intel_4040) that sold for $29 in a similar complete chipset.

Chips are produced by printing multiple copies of the chip design on the surface of a [wafer](/wiki/Wafer_(electronics)), a thin disk of highly pure silicon. Smaller chips can be printed in greater numbers on the same wafer, decreasing their relative price. Additionally, wafers always include some number of tiny physical defects that are scattered across the surface. Any chip printed in that location will fail and has to be discarded. Smaller chips mean any single copy is less likely to be printed on a defect. For both of these reasons, the cost of the final product is strongly dependent on the size of the chip design.

The original 6800 chips were intended to be 180 by 180 [mils](/wiki/Thousandth_of_an_inch) (4.6 mm × 4.6 mm), but layout was completed at 212 by 212 mils (5.4 mm × 5.4 mm), or an area of 29.0 mm2. For the new design, the cost goal demanded a size goal of 153 by 168 mils (3.9 mm × 4.3 mm), or an area of 16.6 mm2, roughly half that of the 6800. Several new techniques would be needed to hit this goal.

### Moving to NMOS

Two significant advances arrived in the market just as the 6502 was being designed that provided significant cost reductions. The first was the move to [depletion-load NMOS](/wiki/Depletion-load_NMOS). The 6800 used an early [NMOS](/wiki/NMOS_logic) process, enhancement mode, that required three supply voltages. One of the 6800's headlining features was an onboard [voltage doubler](/wiki/Voltage_doubler) that allowed a single +5 V supply be used for +5, −5 and +12 V internally, as opposed to other chips of the era like the [Intel 8080](/wiki/Intel_8080) that required three separate supply pins. While this feature reduced the complexity of the power supply and pin layout, it still required separate power lines to the various gates on the chip, driving up complexity and size. By moving to the new depletion-load design, a single +5 V supply was all that was needed, eliminating all of this complexity.

A further advantage was that depletion-load designs used less power while switching, thus running cooler and allowing higher operating speeds. Another practical offshoot is that the clock signal for earlier [CPUs](/wiki/Central_processing_unit) had to be strong enough to survive all the dissipation as it traveled through the circuits, which almost always required a separate external chip that could supply a powerful signal. With the reduced power requirements of depletion-load design, the clock could be moved onto the chip, simplifying the overall computer design. These changes greatly reduced complexity and the cost of implementing a complete system.

A wider change taking place in the industry was the introduction of [projection masking](/wiki/Projection_mask). Previously, chips were patterned onto the surface of the wafer by placing a [mask](/wiki/Photomask) on the surface of the wafer and then shining a bright light on it. The masks often picked up tiny bits of dirt or [photoresist](/wiki/Photoresist) as they were lifted off the chip, causing flaws in those locations on any subsequent masking. With complex designs like CPUs, 5 or 6 such masking steps would be used, and the chance that at least one of these steps would introduce a flaw was very high. In most cases, 90% of such designs were flawed, resulting in a 10% yield. The price of the working examples had to cover the production cost of the 90% that were thrown away.

In 1973, [Perkin-Elmer](/wiki/Perkin-Elmer) introduced the [Micralign](/wiki/Micralign) system, which projected an image of the mask on the wafer instead of requiring direct contact. Masks no longer picked up dirt from the wafers and lasted on the order of 100,000 uses rather than 10. This eliminated step-to-step failures and the high flaw rates formerly seen on complex designs. Yields on CPUs immediately jumped from 10% to 60 or 70%. This meant the price of the CPU declined roughly the same amount and the microprocessor suddenly became a commodity device.

MOS Technology's existing fabrication lines were based on the older [PMOS](/wiki/PMOS_logic) technology, they had not yet begun to work with [NMOS](/wiki/NMOS_logic) when the team arrived. Paivinen promised to have an NMOS line up and running in time to begin the production of the new CPU. He delivered on the promise, the new line was ready by June 1975.

### Design notes

Chuck Peddle, Rod Orgill, and Wil Mathys designed the initial architecture of the new processors. A September 1975 article in *[EDN](/wiki/EDN_(magazine))* magazine gives this summary of the design:

> The MOS Technology 650X family represents a conscious attempt of eight former Motorola employees who worked on the development of the 6800 system to put out a part that would replace and outperform the 6800, yet undersell it. With the benefit of hindsight gained on the 6800 project, the MOS Technology team headed by Chuck Peddle, made the following architectural changes in the Motorola CPU…

The main change in terms of chip size was the elimination of the [tri-state drivers](/wiki/Tri-state_driver) from the address bus outputs. A three-state bus has states for *1*, *0* and *high impedance*. The last state is used to allow other devices to access the bus, and is typically used for [multiprocessing](/wiki/Multiprocessing), or more commonly in these roles, for [direct memory access](/wiki/Direct_memory_access) (DMA). While useful, this feature is expensive in terms of on-chip circuitry. The 6502 simply removed this feature, in keeping with its design as an inexpensive controller being used for specific tasks and communicating with simple devices. Peddle suggested that anyone who required this style of access could implement it with a [74158](/wiki/Multiplexer#List_of_ICs_which_provide_multiplexing).

The next major difference was to simplify the registers. To start with, one of the two [accumulators](/wiki/Accumulator_(computing)) was removed. General-purpose registers like accumulators have to be accessed by many parts of the instruction decoder, and thus require significant amounts of wiring to move data to and from their storage. Two accumulators makes many coding tasks easier but costs the chip design itself significant complexity. Further savings were made by reducing the [stack register](/wiki/Stack_register) from 16 to 8 bits, meaning that the stack could only be 256 bytes long, which was enough for its intended role as a microcontroller.

The 16-bit IX [index register](/wiki/Index_register) was split in two, becoming X and Y. More importantly, the style of access changed. In the 6800, IX held a 16-bit address which was offset by an 8-bit number stored with the instruction and added to the address. In the 6502 (and most other contemporary designs), the 16-bit base address was stored in the instruction, and the 8-bit X or Y was added to it.

Finally, the instruction set was simplified, simplifying the decoder and control logic. Of the original 72 instructions in the 6800, 56 were implemented. Among those removed were instructions that operated between the 6800's two accumulators, and several branch instructions inspired by the [PDP-11](/wiki/PDP-11).

The chip's high-level design had to be turned into drawings of transistors and interconnects. At MOS Technology, the layout was a very manual process done with colored pencils and [vellum paper](/wiki/Vellum_paper). The layout consisted of thousands of polygon shapes on six different drawings; one for each layer of the fabrication process. Given the size limits, the entire chip design had to be constantly considered. Mensch and Paivinen worked on the [instruction decoder](/wiki/Instruction_decoder) while Mensch, Peddle and Orgill worked on the ALU and registers. A further advance, developed at a party, was a way to share some of the internal wiring to allow the ALU to be reduced in size.

Despite their best efforts, the final design ended up being larger than the original target. The first 6502 chips were 168 by 183 mils (4.3 mm × 4.6 mm), for an area of 19.8 mm2. The original version of the processor had no rotate right (ROR) capability, so the instruction was omitted from the original documentation. The next iteration of the design shrank the chip and added the rotate right capability, and ROR was included in revised documentation.

### Introducing the 6501 and 6502

Introductory advertisement for the MOS Technology MCS6501 and MCS6502 microprocessors

MOS would introduce two microprocessors based on the same underlying design: the 6501 would plug into the same socket as the Motorola 6800, while the 6502 re-arranged the pinout to support an on-chip clock oscillator. Both would work with other support chips designed for the 6800. They would not run 6800 software because they had a different instruction set, different registers, and mostly different addressing modes. Rod Orgill was responsible for the 6501 design; he had assisted John Buchanan at Motorola on the 6800. Bill Mensch did the 6502; he was the designer of the 6820 PIA at Motorola. Harry Bawcom, Mike Janes and Sydney-Anne Holt helped with the layout.

MOS Technology's microprocessor introduction was different from the traditional months-long product launch. The first run of a new integrated circuit is normally used for internal testing and shared with select customers as [engineering samples](/wiki/Engineering_sample). These chips often have minor design defects that will be corrected before production begins. Chuck Peddle's goal was to sell the first run 6501 and 6502 chips to the attendees at the WESCON trade show in San Francisco beginning on September 16, 1975. Peddle was a very effective spokesman and the MOS Technology microprocessors were extensively covered in the trade press. One of the earliest was a full-page story on the MCS6501 and MCS6502 microprocessors in the July 24, 1975 issue of *Electronics* magazine. Stories also ran in *[EE Times](/wiki/EE_Times)* (August 24, 1975), *EDN* (September 20, 1975), *Electronic News* (November 3, 1975), *Byte* (November 1975) and *Microcomputer Digest* (November 1975). Advertisements for the 6501 appeared in several publications the first week of August 1975. The 6501 would be for sale at WESCON for $20 each. In September 1975, the advertisements included both the 6501 and the 6502 microprocessors. The 6502 would cost only $25 (equivalent to $150 in 2025).

When MOS Technology arrived at Wescon, they found that exhibitors were not permitted to sell anything on the show floor. They rented the MacArthur Suite at the [St. Francis Hotel](/wiki/Westin_St._Francis) and directed customers there to purchase the processors. At the suite, the processors were stored in large jars to imply that the chips were in production and readily available. The customers did not know the bottom half of each jar contained non-functional chips. The chips were $20 and $25 while the documentation package was an additional $10. Users were encouraged to make [photocopies](/wiki/Photocopies) of the documents, an inexpensive way for MOS Technology to distribute product information. The preliminary data sheets listed just 55 instructions and excluded the Rotate Right (ROR) instruction, which was not supported on these early chips. The reviews in *Byte* and *EDN* noted the lack of the ROR instruction. The next revision of the layout fixed this problem and the May 1976 datasheet listed 56 instructions. Peddle wanted every interested engineer and hobbyist to have access to the chips and documentation, whereas other semiconductor companies only wanted to deal with "serious" customers. For example, [Signetics](/wiki/Signetics) was introducing the [2650](/wiki/Signetics_2650) microprocessor and its advertisements asked readers to write for information on their company letterhead.

### Motorola lawsuit

The May 1976 datasheet omitted the 6501 microprocessor that was in the [August 1975](/wiki/File:MCS650X_Datasheet_Aug_1975_cover.jpg) version.

The 6501/6502 introduction in print and at Wescon was a success. The press coverage got Motorola's attention, precipitating pricing adjustments and lawsuits. In October 1975, Motorola reduced the price of a single 6800 microprocessor from $175 to $69. The $300 system design kit was reduced to $150 and it now came with a printed circuit board. On November 3, 1975, Motorola sought an injunction in Federal Court to stop MOS Technology from making and selling microprocessor products. They also filed a lawsuit claiming patent infringement and misappropriation of trade secrets. Motorola claimed that seven former employees joined MOS Technology to create that company's microprocessor products.

Motorola was a billion-dollar company with a plausible case and expensive lawyers. On October 30, 1974, Motorola had filed numerous patent applications on the microprocessor family and was granted twenty-five patents. The first was in June 1976 and the second was to Bill Mensch on July 6, 1976, for the 6820 PIA chip layout. These patents covered the 6800 bus and how the peripheral chips interfaced with the microprocessor. Motorola began making transistors in 1950 and had a portfolio of semiconductor patents. Allen-Bradley decided not to fight this case and sold their interest in MOS Technology back to the founders. Four of the former Motorola engineers were named in the suit: Chuck Peddle, Will Mathys, Bill Mensch and Rod Orgill. All were named inventors in the 6800 patent applications. During the discovery process, Motorola found that one engineer, Mike Janes, had ignored Peddle's instructions and brought his 6800 design documents to MOS Technology. In March 1976, the now independent MOS Technology was running out of money and had to settle the case. They agreed to drop the 6501 processor, pay Motorola $200,000 and return the documents that Motorola contended were confidential. Both companies agreed to [cross-license](/wiki/Cross-licensing) microprocessor patents. That May, Motorola dropped the price of a single 6800 microprocessor to $35. By November, [Commodore](/wiki/Commodore_International) had acquired MOS Technology.

### Computers and games

With legal troubles behind them, MOS was still left with the problem of getting developers to try their processor, prompting Chuck Peddle to design the MDT650 development system. Another group inside the company designed the [KIM-1](/wiki/KIM-1), which was sold semi-complete and could be turned into a usable system with the addition of a 3rd party [computer terminal](/wiki/Computer_terminal) and [compact cassette](/wiki/Compact_cassette) drive. While it sold well to its intended market, the company found the KIM-1 also sold well to hobbyists and tinkerers. The related Rockwell [AIM-65](/wiki/AIM-65) control, training, and development system also did well. The software in the AIM 65 was based on that in the MDT. Another roughly similar product was the Synertek [SYM-1](/wiki/SYM-1).

One of the first external uses for the design was the [Apple I](/wiki/Apple_I) microcomputer, introduced in 1976. The 6502 was next used in the [Commodore PET](/wiki/Commodore_PET) and [Apple II](/wiki/Apple_II), both released in 1977. It was later used in the [Atari 8-bit computers](/wiki/Atari_8-bit_computers), [Acorn Atom](/wiki/Acorn_Atom), [BBC Micro](/wiki/BBC_Micro), [VIC-20](/wiki/VIC-20) and other designs both for home computers and business, such as [Ohio Scientific](/wiki/Ohio_Scientific) and [Oric computers](/wiki/Oric_computers). The [6510](/wiki/MOS_Technology_6510), a direct successor of the 6502 with a digital I/O port and a [tri-state](/wiki/Tri-state_buffer) address bus, was the CPU utilized in the best-selling [Commodore 64](/wiki/Commodore_64) home computer.

Another important use of the 6500 family was in video games. The first to make use of the processor design was the 1977 Atari VCS, later renamed the [Atari 2600](/wiki/Atari_2600). The VCS used a 6502 variant named the [6507](/wiki/MOS_Technology_6507), which had fewer pins, so it could address only 8 [KB](/wiki/Kilobyte) of memory. Millions of the Atari consoles would be sold, each with a MOS processor. Another significant use was by the [Nintendo Entertainment System (NES) and Famicom](/wiki/Nintendo_Entertainment_System). The 6502 used in the NES was a [second source](/wiki/Second_source) version by [Ricoh](/wiki/Ricoh), a partial [system on a chip](/wiki/System_on_a_chip), that lacked the [binary-coded decimal](/wiki/Binary-coded_decimal) mode but added 22 memory-mapped registers and on-die hardware for sound generation, joypad reading, and [sprite](/wiki/Sprite_(computer_graphics)) list [DMA](/wiki/Direct_memory_access). Called [2A03](/wiki/Ricoh_2A03) in [NTSC](/wiki/NTSC) consoles and [2A07](/wiki/2A07) in [PAL](/wiki/PAL) consoles, this processor was produced exclusively for [Nintendo](/wiki/Nintendo).

6502 or variants were used in all of Commodore's [floppy disk drives](/wiki/Floppy_disk_drive) for all of their 8-bit computers, from the PET line through the Commodore 128D, including the Commodore 64. 8-inch PET drives had two 6502 processors. Atari used the same 6507 used in the Atari 2600 for its [810](/wiki/Atari_810) and [1050](/wiki/Atari_1050) disk drives used for all of their 8-bit computer line, from the 400/800 through the XEGS.

In the 1980s, a popular electronics magazine [Elektor](/wiki/Elektor) used the processor in its microprocessor development board [Junior Computer](/wiki/Elektor_Junior_Computer).

The CMOS successor to the 6502, the [WDC 65C02](/wiki/WDC_65C02), also saw use in home computers and video game consoles. Apple used it in the Apple II line, starting with the [Apple IIc](/wiki/Apple_IIc) and later variants of the [Apple IIe](/wiki/Apple_IIe), and also offered a kit to upgrade older IIe systems with the new processor. The [Hudson Soft HuC6280](/wiki/Hudson_Soft_HuC6280) chip used in the [TurboGrafx-16](/wiki/TurboGrafx-16) was based on a 65C02 core. The [Atari Lynx](/wiki/Atari_Lynx) used a custom chip named "Mikey" designed by [Epyx](/wiki/Epyx) which included a VLSI VL65NC02 licensed cell. The G65SC12 by [GTE Microcircuits](/wiki/GTE_Microcircuits) (renamed California Micro Devices) variant was used in the [BBC Master](/wiki/BBC_Master). Some models of the BBC Master also included an additional G65SC102 co-processor.

- Home computers and video game consoles using the 6502 or its variants
- [Acorn Atom](/wiki/Acorn_Atom)
- [Acorn Electron](/wiki/Acorn_Electron)
- [Apple I](/wiki/Apple_I)
- [Apple II](/wiki/Apple_II)
- [Apple IIe](/wiki/Apple_IIe)
- [Atari 2600](/wiki/Atari_2600)
- [Atari 5200](/wiki/Atari_5200)
- [Atari 7800](/wiki/Atari_7800)
- [Atari 800](/wiki/Atari_8-bit_computers)
- [Atari Lynx](/wiki/Atari_Lynx)
- [BBC Master](/wiki/BBC_Master)
- [Baby! 1](/wiki/Baby!_1)
- [BBC Micro](/wiki/BBC_Micro)
- [Commodore PET](/wiki/Commodore_PET)
- [Commodore VIC-20](/wiki/VIC-20)
- [Commodore 64](/wiki/Commodore_64)
- [Commodore 128](/wiki/Commodore_128)
- [Family Computer (Famicom)](/wiki/Nintendo_Entertainment_System)
- [Nintendo Entertainment System](/wiki/Nintendo_Entertainment_System)
- [Ohio Scientific Challenger 4P](/wiki/Ohio_Scientific)
- [Orao](/wiki/Orao_(computer))
- [Oric-1](/wiki/Oric-1)
- [Oric Atmos](/wiki/Oric_Atmos)
- [TurboGrafx-16](/wiki/TurboGrafx-16)

## Programmers model

6502 processor die. The regular section at the top is the instruction decoding ROM, the irregular section in the center is the control logic, and at the bottom are the registers (right) and the ALU (left). The data bus connections are along the lower right, and the address bus along the bottom and lower left.

6502 pin configuration (40-pin [DIP](/wiki/Dual_in-line_package))

**MOS 6502 registers**

|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | 14 | 13 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 | *(bit position)* |
| **Main registers** | | | | | | | | | | | | | | | | |
|  | | | | | | | | A | | | | | | | | [**A**ccumulator](/wiki/Accumulator_(computing)) |
| **[Index registers](/wiki/Index_registers)** | | | | | | | | | | | | | | | | |
|  | | | | | | | | X | | | | | | | | **X** [index](/wiki/Index_register) |
|  | | | | | | | | Y | | | | | | | | **Y** index |
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | S | | | | | | | | [**S**tack pointer](/wiki/Stack_pointer) |
| **[Program counter](/wiki/Program_counter)** | | | | | | | | | | | | | | | | |
| PC | | | | | | | | | | | | | | | | **P**rogram **C**ounter |
| **[Status register](/wiki/Status_register)** | | | | | | | | | | | | | | | | |
|  | | | | | | | | [N](/wiki/Negative_flag) | [V](/wiki/Overflow_flag) | - | [B](#BRK_Flag) | [D](/wiki/Binary-coded_decimal) | [I](/wiki/Interrupt_flag) | [Z](/wiki/Zero_flag) | [C](/wiki/Carry_flag) | **P**rocessor flags |

The 6502 is a [little-endian](/wiki/Little-endian) [8-bit](/wiki/8-bit_computing) processor with a [16-bit](/wiki/16-bit_computing) [address bus](/wiki/Address_bus). The original versions were fabricated using an 8 µm process technology with a [die size](/wiki/Die_(integrated_circuit)) of 3.9 mm × 4.3 mm (153 by 168 mils), for a total area of 16.6 mm2.

The internal logic runs at the same speed as the external clock rate. It featured a simple two-stage pipeline; on each cycle, the processor fetches one byte from memory and processes another. This means that any single instruction can take as few as two cycles to complete, depending on the number of operands that instruction uses. For comparison, the [Zilog Z80](/wiki/Zilog_Z80) required two cycles to fetch memory, and the minimum instruction time was four cycles. Thus, despite the lower clock speeds compared to competing designs, typically in the neighborhood of 1 to 2 [MHz](/wiki/Megahertz), the 6502's performance was competitive with CPUs using significantly faster clocks. This is partly due to a simple state machine implemented by [combinational (clockless) logic](/wiki/Combinational_logic) to a greater extent than in many other designs; the two-phase clock (supplying two synchronizations per cycle) could thereby control the machine cycle directly.

This design also led to one useful design note of the 6502, and the 6800 before it. Because the chip only accessed memory during a certain part of the clock cycle, other chips in a system could access memory during those times when the 6502 was off the bus. This was sometimes known as *hidden access*. This technique was widely used by computer systems; they would use memory capable of access at 2 MHz, and then run the CPU at 1 MHz. This guaranteed that the CPU and video hardware could interleave their accesses, with a total performance matching that of the memory device. Because this access was every other cycle, there was no need to signal the CPU to avoid using the bus, making this sort of access easy to implement without any bus logic. When faster memories became available in the 1980s, newer machines could use this same technique while running at higher clock rates; the [BBC Micro](/wiki/BBC_Micro) used newer RAM that allowed its CPU to run at 2 MHz while still using the same bus sharing techniques.

Like most simple CPUs of the era, the dynamic [NMOS](/wiki/NMOS_logic) 6502 chip is not sequenced by [microcode](/wiki/Microcode) but decoded directly using a dedicated [PLA](/wiki/Programmable_logic_array). The decoder occupied about 15% of the chip area. This compares to later microcode-based designs like the [Motorola 68000](/wiki/Motorola_68000), where the microcode ROM and decoder engine represented about a third of the gates in the system.

### Registers

Like its precursor, the 6800, the 6502 has very few [registers](/wiki/Processor_register). They include

- `A` = 8-bit [accumulator](/wiki/Accumulator_(computing))
- `P` = 7-bit processor [status](/wiki/Status_register)
  - `n` = [Negative](/wiki/Negative_flag)
  - `v` = [Overflow](/wiki/Overflow_flag)
  - `b` = [Break](#BRK_Flag) (only in stack values, not in hardware)
  - `d` = [Decimal](/wiki/Binary-coded_decimal)
  - `i` = [Interrupt disable](/wiki/Interrupt_flag)
  - `z` = [Zero](/wiki/Zero_flag)
  - `c` = [Carry](/wiki/Carry_flag)
- `PC` = 16-bit [program counter](/wiki/Program_counter)
- `S` = 8-bit [stack pointer](/wiki/Stack_pointer)
- `X` = 8-bit [index](/wiki/Index_register)
- `Y` = 8-bit index

This compares to a contemporaneous competitor, the [Intel 8080](/wiki/Intel_8080), which likewise has one 8-bit accumulator and a 16-bit program counter, but has six more general-purpose 8-bit registers (which can be combined into three 16-bit pointers) and a larger 16-bit stack pointer.

In order to make up somewhat for the lack of registers, the 6502 includes a *[zero page](/wiki/Zero_page)* addressing mode that uses one address byte in the instruction instead of the two needed to address the full 64 KB of memory. This provides fast access to the first 256 bytes of RAM by using shorter instructions. For instance, an instruction to add a value from memory to the value in the accumulator would normally be three bytes, one for the instruction and two for the 16-bit address. Using the zero page reduces this to an 8-bit address, reducing the total instruction length to two bytes, and thus improving instruction performance.

The stack address space is [hardwired](https://en.wiktionary.org/wiki/Hardwired) to memory page `$01`, i.e. the address range `$0100`–`$01FF` (`256`–`511`). Software access to the stack is done via four implied addressing mode instructions, whose functions are to push or pop (pull) the accumulator or the processor status register. The same stack is also used for subroutine calls via the JSR (jump to subroutine) and RTS (return from subroutine) instructions and for [interrupt](/wiki/Interrupt) handling.

### Addressing

The chip uses the index and stack registers effectively with several [addressing modes](/wiki/Addressing_mode), including a fast *zero page* mode, similar to that found on the [PDP-8](/wiki/PDP-8), that accesses memory locations from addresses 0 to 255 with a single 8-bit address (saving the cycle normally required to fetch the high-order byte of the address)—code for the 6502 uses the zero page much as code for other processors would use registers. On some 6502-based microcomputers with an operating system, the [operating system](/wiki/Operating_system) uses most of the zero page, leaving only a handful of locations for the user.

Addressing modes also include *implied* (1-byte instructions); *absolute* (3 bytes); *indexed absolute* (3 bytes); *indexed zero-page* (2 bytes); *relative* (2 bytes); *accumulator* (1); *indirect,x* and *indirect,y* (2); and *immediate* (2). Branch instructions use a signed 8-bit offset relative to the instruction after the branch; the numerical range −128..127 therefore translates to 128 bytes backward and 127 bytes forward from the instruction following the branch (which is 126 bytes backward and 129 bytes forward from the start of the branch instruction). Accumulator mode operates on the accumulator register and does not need any [operand](/wiki/Operand) data. Immediate mode uses an 8-bit [literal](/wiki/Literal_(computer_programming)) operand.

The indirect modes are useful for [array](/wiki/Array_(data_type)) processing and pointer-based data structures. With the 5 or 6 cycle *indirect,y* mode, the 8-bit Y register is added to a 16-bit base address read from zero page, which is located by a single byte following the opcode. The Y register is therefore an *index* register in the sense that it is used to hold an actual *index*. Incrementing the index register to walk the array byte-wise takes only two additional cycles. With the less frequently used *indirect,x* mode, the effective address for the operation is found at the zero page address formed by adding the second byte of the instruction to the contents of the X register. Using the indexed modes, the zero page effectively acts as a set of up to 128 additional (low-performance) address registers.

The 6502 is capable of performing addition and subtraction in binary or [binary-coded decimal](/wiki/Binary-coded_decimal). Placing the CPU into BCD mode with the `SED` (set D flag) instruction results in decimal arithmetic, in which `$99 + $01` would result in $00 and the carry (C) flag being set. In binary mode (`CLD`, clear D flag), the same operation would result in $9A and the carry flag being cleared. Other than [Atari BASIC](/wiki/Atari_BASIC), BCD mode was seldom used in home-computer applications.

See the [Hello world!](https://en.wikibooks.org/wiki/Computer_Programming/Hello_world#Accumulator_+_index_register_machine:_MOS_Technology_6502,_CBM_KERNEL,_MOS_assembler_syntax) article for a simple but characteristic example of 6502 [assembly language](/wiki/Assembly_language).

### Instructions and opcodes

6502 instruction [operation codes](/wiki/Opcode) (*opcodes*) are 8 bits long and have the general form AAABBBCC, where AAA and CC define the opcode, and BBB defines the addressing mode. For example, the `ORA` instruction performs a bitwise OR on the bits in the accumulator with another value. The instruction opcode is of the form 000bbb01, where bbb may be 010 for an immediate mode value (constant), 001 for zero-page fixed address, 011 for an absolute address, and so on. This pattern is not universal, as there are exceptions, but it allows opcode values to be easily converted to assembly mnemonics for the majority of instructions, handling the edge cases with special-purpose code.

Of the 256 possible opcodes available using an 8-bit pattern, the original 6502 uses 151 of them, organized into 56 instructions with (possibly) multiple [addressing modes](/wiki/Addressing_mode). Depending on the instruction and addressing mode, the opcode may require zero, one or two additional bytes for operands. Hence 6502 machine instructions vary in length from one to three bytes. The operand is stored in the 6502's customary [little-endian format](/wiki/Endianness).

Each CPU machine instruction takes up a certain number of clock cycles, usually equal to the number of memory accesses. For example, the absolute indexing mode of the ORA instruction takes 4 clock cycles; 3 cycles to read the instruction and 1 cycle to read the value of the absolute address. If no memory is accessed, the number of clock cycles is two. The minimum clock cycles for any instruction is two. When using indexed addressing, if the result crosses a page boundary an extra clock cycle is added. Also, when a zero page address is used in indexing mode (e.g. zp,X) an extra clock cycle is added.

The [65C816](/wiki/WDC_65C816), the 16-bit [CMOS](/wiki/CMOS) descendant of the 6502, also supports 24-bit addressing, which results in instructions being assembled with three-byte operands, also arranged in little-endian format.

The remaining 105 opcodes are undefined. In the original design, instructions where the low-order 4 bits (*nibble*) were 3, 7, B or F were not used, providing room for future expansion. Likewise, the $x2 column had only a single entry, `LDX #constant`. The remaining 25 empty slots were distributed. Some of the empty slots were used in the 65C02 to provide both new instructions and variations on existing ones with new addressing modes. The $xF instructions were initially left free to allow 3rd-party vendors to add their own instructions, but later versions of the 65C02 standardized a set of [bit manipulation](/wiki/Bit_manipulation) instructions developed by [Rockwell Semiconductor](/wiki/Rockwell_Semiconductor).

### Assembly language

A 6502 [assembly language](/wiki/Assembly_language) statement consists of a three-character instruction [mnemonic](/wiki/Mnemonic), followed by any [operands](/wiki/Operand). Instructions that do not take a separate operand but target a single register based on the addressing mode combine the target register in the instruction mnemonic, so the assembler uses `INX` as opposed to `INC X` to increment the X register.

### Instruction table

Opcode matrix for the 6502 instruction set

|  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Addressing modes: ***A*** – accumulator, ***#*** – immediate, ***zpg*** – zero page, ***abs*** – absolute, ***ind*** – indirect, ***X*** – indexed by X register, ***Y*** – indexed by Y register, ***rel*** – relative | | | | | | | | | | | | |
| High nibble | Low nibble | | | | | | | | | | | |
| 0 | 1 | 2 | 4 | 5 | 6 | 8 | 9 | A | C | D | E |
| 0 | BRK | ORA (*ind*,X) |  |  | ORA *zpg* | ASL *zpg* | PHP | ORA # | ASL A |  | ORA *abs* | ASL *abs* |
| 1 | BPL *rel* | ORA (*ind*),Y |  |  | ORA *zpg*,X | ASL *zpg*,X | CLC | ORA *abs*,Y |  |  | ORA *abs*,X | ASL *abs*,X |
| 2 | JSR *abs* | AND (*ind*,X) |  | BIT *zpg* | AND *zpg* | ROL *zpg* | PLP | AND # | ROL A | BIT *abs* | AND *abs* | ROL *abs* |
| 3 | BMI *rel* | AND (*ind*),Y |  |  | AND *zpg*,X | ROL *zpg*,X | SEC | AND *abs*,Y |  |  | AND *abs*,X | ROL *abs*,X |
| 4 | RTI | EOR (*ind*,X) |  |  | EOR *zpg* | LSR *zpg* | PHA | EOR # | LSR A | JMP *abs* | EOR *abs* | LSR *abs* |
| 5 | BVC *rel* | EOR (*ind*),Y |  |  | EOR *zpg*,X | LSR *zpg*,X | CLI | EOR *abs*,Y |  |  | EOR *abs*,X | LSR *abs*,X |
| 6 | RTS | ADC (*ind*,X) |  |  | ADC *zpg* | ROR *zpg* | PLA | ADC # | ROR A | JMP (*ind*) | ADC *abs* | ROR *abs* |
| 7 | BVS *rel* | ADC (*ind*),Y |  |  | ADC *zpg*,X | ROR *zpg*,X | SEI | ADC *abs*,Y |  |  | ADC *abs*,X | ROR *abs*,X |
| 8 |  | STA (*ind*,X) |  | STY *zpg* | STA *zpg* | STX *zpg* | DEY |  | TXA | STY *abs* | STA *abs* | STX *abs* |
| 9 | BCC *rel* | STA (*ind*),Y |  | STY *zpg*,X | STA *zpg*,X | STX *zpg*,Y | TYA | STA *abs*,Y | TXS |  | STA *abs*,X |  |
| A | LDY # | LDA (*ind*,X) | LDX # | LDY *zpg* | LDA *zpg* | LDX *zpg* | TAY | LDA # | TAX | LDY *abs* | LDA *abs* | LDX *abs* |
| B | BCS *rel* | LDA (*ind*),Y |  | LDY *zpg*,X | LDA *zpg*,X | LDX *zpg*,Y | CLV | LDA *abs*,Y | TSX | LDY *abs*,X | LDA *abs*,X | LDX *abs*,Y |
| C | CPY # | CMP (*ind*,X) |  | CPY *zpg* | CMP *zpg* | DEC *zpg* | INY | CMP # | DEX | CPY *abs* | CMP *abs* | DEC *abs* |
| D | BNE *rel* | CMP (*ind*),Y |  |  | CMP *zpg*,X | DEC *zpg*,X | CLD | CMP *abs*,Y |  |  | CMP *abs*,X | DEC *abs*,X |
| E | CPX # | SBC (*ind*,X) |  | CPX *zpg* | SBC *zpg* | INC *zpg* | INX | SBC # | NOP | CPX *abs* | SBC *abs* | INC *abs* |
| F | BEQ *rel* | SBC (*ind*),Y |  |  | SBC *zpg*,X | INC *zpg*,X | SED | SBC *abs*,Y |  |  | SBC *abs*,X | INC *abs*,X |
| Blank opcodes (e.g., **F2**) and all opcodes whose low nibbles are **3**, **7**, **B** and **F** are undefined in the 6502 instruction set. | | | | | | | | | | | | |

### Example code

The following 6502 [assembly language](/wiki/Assembly_language) [source code](/wiki/Source_code) is for a subroutine named `TOLOWER`, which copies a [null-terminated](/wiki/Null-terminated_string) [character string](/wiki/String_(computer_science)) from one location to another, converting upper-case letter characters to lower-case letters. The string being copied is the "source", and the string into which the converted source is stored is the "destination".

|  |  |
| --- | --- |
| ``` 0080   0080  00 04 0082  00 05   0600   0600  A0 00   0602  B1 80 0604  F0 11   0606  C9 41 0608  90 06   060A  C9 5B 060C  B0 02   060E  09 20   0610  91 82 0612  C8    0613  D0 ED         0615  38    0616  60   0617  91 82 0619  18    061A  60   061B ``` | ``` ; TOLOWER: ; ;   Convert a null-terminated character string to all lower case. ;   Maximum string length is 255 characters, plus the null term- ;   inator. ; ; Parameters: ; ;   SRC – Source string address ;   DST – Destination string address ;         ORG $0080 ; SRC     .WORD $0400     ;source string pointer DST     .WORD $0500     ;destination string pointer ;         ORG $0600       ;execution start address ; TOLOWER LDY #$00        ;starting index ; LOOP    LDA (SRC),Y     ;get from source string         BEQ DONE        ;end of string ;         CMP #'A'        ;if lower than UC alphabet...         BCC SKIP        ;copy unchanged ;         CMP #'Z'+1      ;if greater than UC alphabet...         BCS SKIP        ;copy unchanged ;         ORA #%00100000  ;convert to lower case ; SKIP    STA (DST),Y     ;store to destination string         INY             ;bump index         BNE LOOP        ;next character ; ; NOTE: If Y wraps the destination string will be left in an undefined ;  state. We set carry to indicate this to the calling function. ;         SEC             ;report string too long error &...         RTS             ;return to caller ; DONE    STA (DST),Y     ;terminate destination string         CLC             ;report conversion completed &...         RTS             ;return to caller ;         .END ``` |

## IC hardware design

See also: [Interrupts in 65xx processors](/wiki/Interrupts_in_65xx_processors)

6502 processor die with drawn-in NMOS transistors and labels hinting at the functionality of the 6502's components

The processor's [non-maskable interrupt](/wiki/Non-maskable_interrupt) (NMI) input is [edge sensitive](/wiki/Interrupt#Edge-triggered), which means that the interrupt is triggered by the falling edge of the signal rather than its level. Consequently a [wired-OR](/wiki/Wired-OR) interrupt circuit cannot be readily supported. However, this also prevents nested NMI interrupts from occurring until the interrupt source hardware makes the NMI input inactive again, often under control of the NMI [interrupt handler](/wiki/Interrupt_handler).

The simultaneous assertion of the NMI and [IRQ](/wiki/Interrupt_request) (maskable) hardware interrupt lines causes IRQ to be ignored. However, if the IRQ line remains asserted after the servicing of the NMI, the processor will almost immediately respond to IRQ, as IRQ is [level sensitive](/wiki/Interrupt#Level-triggered). Thus a sort of built-in interrupt priority was established in the 6502 design. (The first opcode of the NMI handler is executed before the IRQ is detected again.)

The B flag is set by the 6502's periodically sampling its NMI edge detector's output and its IRQ input. The IRQ signal being driven low is only recognized though if IRQs are not masked by the I flag. If in this way a NMI request or (maskable) IRQ is detected the B flag is set to zero and causes the processor to execute the BRK instruction next instead of executing the next instruction based on the program counter.

The BRK instruction then pushes the processor status onto the stack, with the B flag bit set to zero. At the end of its execution the BRK instruction resets the B flag's value to one. This is the only way the B flag can be modified. If an instruction other than the BRK instruction pushes the B flag onto the stack as part of the processor status the B flag always has the value one.

A high-to-low transition on the SO input pin will set the processor's overflow status bit. This can be used for fast response to external hardware. For example, a high-speed [polling](/wiki/Polling_(computer_science)) device driver can poll the hardware once in only three cycles using a Branch-on-oVerflow-Clear (`BVC`) instruction that branches to itself until overflow is set by an SO falling transition. The [Commodore 1541](/wiki/Commodore_1541) and other [Commodore](/wiki/Commodore_International) [floppy disk](/wiki/Floppy_disk) drives use this technique to detect when the [serializer](/wiki/Serialization) is ready to transfer another byte of disk data. The system hardware and software design must ensure that an SO will not occur during arithmetic processing and disrupt calculations.

## Variations and derivatives

The 6502 was the most prolific variant of the 65xx series family from [MOS Technology](/wiki/MOS_Technology).

The 6501 and 6502 have 40-pin [DIP](/wiki/Dual_inline_package) packages; the 6503, 6504, 6505, and 6507 are 28-pin DIP versions, for reduced chip and circuit board cost. In all of the 28-pin versions, the pin count is reduced by leaving off some of the high-order address pins and various combinations of function pins, making those functions unavailable.

Pinout differences

| Pin | 6800 | 6501 | 6502 |
| --- | --- | --- | --- |
| 2 | Halt | Ready | Ready |
| 3 | ∅1 (in) | ∅1 (in) | ∅1 (out) |
| 5 | Valid memory address | Valid memory address | N.C. |
| 7 | Bus available | Bus available | SYNC |
| 36 | Data bus enable | Data bus enable | N.C. |
| 37 | ∅2 (in) | ∅2 (in) | ∅0 (in) |
| 38 | N.C. | N.C. | Set overflow flag |
| 39 | Three-state control | N.C. | ∅2 (out) |

Typically, the 12 pins omitted to reduce the pin count from 40 to 28 are the three [not connected](/wiki/Not_connected) (NC) pins, one of the two Vss pins, one of the clock pins, the SYNC pin, the set overflow (SO) pin, either the maskable interrupt or the non-maskable interrupt (NMI), and the four most-significant address lines (A12–A15). The omission of four address pins reduces the external addressability to 4 KB (from the 64 KB of the 6502), though the internal PC register and all effective address calculations remain [16-bit](/wiki/16-bit_computing).

The [6507](/wiki/MOS_Technology_6507) omits both interrupt pins in order to include address line A12, providing 8 KB of external addressability but no interrupt capability. The 6507 was used in the popular [Atari 2600](/wiki/Atari_2600) video game console, the design of which divides the 8 KB memory space in half, allocating the lower half to the console's internal RAM and peripherals, and the upper half to the Game Cartridge, so Atari 2600 cartridges have a 4 KB address limit (and the same capacity limit unless the cartridge contains [bank switching](/wiki/Bank_switching) circuitry).

One popular 6502-based computer, the [Commodore 64](/wiki/Commodore_64), used a modified 6502 CPU, the [6510](/wiki/MOS_Technology_6510). Unlike the 6503–6505 and 6507, the 6510 is a 40-pin chip that adds internal hardware: a 6-bit parallel I/O port mapped to addresses 0000 and 0001. The [6508](/wiki/MOS_Technology_6508) is another chip that, like the 6510, adds internal hardware: 256 bytes of [SRAM](/wiki/Static_random-access_memory) and an 8-bit I/O port similar to those featured by the 6510. Though these chips do not have reduced pin counts compared to the 6502, they need new pins for the added parallel I/O port. In this case, no address lines are among the removed pins.

Variations

| Company | Model | Description |
| --- | --- | --- |
|  | 6502 | A 1 MHz chip used in *[KIM-1](/wiki/KIM-1)* and other single board computers in the mid-1970s. |
|  | 6502A | A 1.5 MHz chip used in *[Asteroids Deluxe](/wiki/Asteroids_Deluxe)* and at 2 MHz in the [BBC Micro](/wiki/BBC_Micro) |
|  | 6502B | Version of the 6502 capable of running at a maximum speed of 3 MHz instead of 2 MHz. The B was used in both the [Apple III](/wiki/Apple_III) and early [Atari 8-bit computers](/wiki/Atari_8-bit_computers), each running at ~1.8 MHz. |
|  | 6502C | The “official” 6502C was a version of the original 6502 able to run at up to 4 MHz. Not to be confused with SALLY, a custom 6502 designed for Atari (and sometimes referred to by them as "6502C") nor with the similarly named [65C02](/wiki/65C02). |
|  | SALLY, C014806, "6502C" | Custom 6502 variant designed for Atari, used in later [Atari 8-bit computers](/wiki/Atari_8-bit_computers) and [Atari 5200](/wiki/Atari_5200) and [Atari 7800](/wiki/Atari_7800) consoles. Has a HALT signal on pin 35 and the R/W signal on pin 36 (these pins are not connected (N/C) on a standard 6502). Pulling HALT low latches the clock, pausing the processor. This was used to allow the video circuitry direct memory access (DMA).  Although sometimes referred to as "6502C" in Atari documentation, this is not the same as the *official* 6502C and the chip itself is never marked as such. |
| MOS | 6503 | Reduced memory addressing capability (4 KB) and no RDY input, in a 28-pin DIP package (with the phase 1 (OUT), SYNC, redundant Vss, and SO pins of the 6502 also omitted). |
| MOS | 6504 | Reduced memory addressing capability (8 KB), no NMI, and no RDY input, in a 28-pin DIP package (with the phase 1 (OUT), SYNC, redundant Vss, and SO pins of the 6502 also omitted). |
| MOS | 6505 | Reduced memory addressing capability (4 KB) and no NMI, in a 28-pin DIP package (with the phase 1 (OUT), SYNC, redundant Vss, and SO pins of the 6502 also omitted). |
| MOS | 6506 | Reduced memory addressing capability (4 KB), no NMI, and no RDY input, but all 3 clock pins of the 6502 (i.e. a 2-phase output clock), in a 28-pin DIP package (with the SYNC, redundant Vss, and SO pins of the 6502 also omitted). |
| MOS | [6507](/wiki/MOS_Technology_6507) | Reduced memory addressing capability (8 KB) and no interrupts, in a 28-pin DIP package (with the phase 1 (OUT), SYNC, redundant Vss, and SO pins of the 6502 also omitted). This chip was used in the [Atari 2600](/wiki/Atari_2600) video game system and in many Atari 8-bit computer peripherals. |
| MOS | [6508](/wiki/MOS_Technology_6508) | Has a built-in 8-bit input/output port and 256 bytes of internal static RAM. |
| MOS | [6509](/wiki/MOS_Technology_6509) | Can address up to 1 MB of RAM as 16 banks of 64 KB and was used in the Commodore [CBM-II](/wiki/CBM-II) series. |
| MOS | [6510](/wiki/MOS_Technology_6510) | Has a built-in 6-bit programmable input/output port and was used in the [Commodore 64](/wiki/Commodore_64). The 8500 is effectively an HMOS version of the 6510, and replaced it in later versions of the C64. |
| MOS | [6512](/wiki/MOS_Technology_6512) 6513 6514 6515 | The MOS Technology 6512, 6513, 6514, and 6515 each rely on an external clock, instead of using an internal clock generator like the 650x (e.g. 6502). This was used to advantage in some designs where the clocks could be run asymmetrically, increasing overall CPU performance. The 6512 is a 6502 with a 2-phase clock input for an external clock oscillator, instead of an on-board clock oscillator. The 6513, 6514 and 6515 are similarly equivalent to (respectively) a 6503, 6504 and 6505 with the same 2-phase clock input.  The 6512 was used in the [BBC Micro B+64](/wiki/BBC_Micro). |
| Ricoh | [RP2A03](/wiki/Ricoh_2A03) RP2A07 | Unlicensed 6502 variants running at ~1.8 MHz including an audio processing unit but lacking the BCD mode, used in the [Nintendo Entertainment System](/wiki/Nintendo_Entertainment_System). |
| MOS | 6591 6592 | [System on a chip](/wiki/System_on_a_chip) designs that utilize a complete [Atari 2600](/wiki/Atari_2600) in a 48-pin DIP package. |
| WDC | [65C02](/wiki/65C02) | [CMOS](/wiki/CMOS) version of the NMOS 6502 that was designed by [Bill Mensch](/wiki/Bill_Mensch) of the [Western Design Center](/wiki/Western_Design_Center) (WDC), featuring reduced power consumption, support for much higher clock speeds, new instructions, new addressing modes for some existing instructions, and correction of NMOS errata, such as the `JMP ($xxFF)` bug. |
| CSG, MOS | [65CE02](/wiki/CSG_65CE02) | CMOS variant developed by the [Commodore Semiconductor Group](/wiki/Commodore_Semiconductor_Group) (CSG), formerly MOS Technology. The 65CE02 provides a further enhanced instruction set from the 65C02, featuring a third indexing register (Z), base page register, 16-bit stack and faster program execution with the minimal instruction timing reduced from 2 to 1 clock cycles. |
| Rockwell | R6511Q  R6500/11, R6500/12, R6500/15 "*One-Chip Microcomputers*" | Enhanced versions of the 6502-based processor, also including individual bit manipulation operations (RMB, SMB, BBR and BBS), on-chip 192-byte zero-page RAM, [UART](/wiki/UART), etc. |
| Rockwell | R65F11 R65F12 | The Rockwell R65F11 (introduced in 1983) and the later R65F12 are enhanced versions of the 6502-based processor, also including individual bit manipulation operations (RMB, SMB, BBR and BBS), on-chip zero-page RAM, on-chip [Forth](/wiki/Forth_(programming_language)) kernel ROM, a UART, etc. |
| GTE | G65SC12 | Drop in 6502 CMOS variant without individual bit manipulation operations (RMB, SMB, BBR and BBS). This was used in the [BBC Master](/wiki/BBC_Master). |
| GTE | G65SC102 | Software compatible with the 6502, but has a slightly different pinout and oscillator circuit. The [BBC Master](/wiki/BBC_Master) Turbo included the 4 MHz version of this CPU on a coprocessor card, which could also be bought separately and added to the Master 128. |
| Rockwell | R65C00 R65C21 R65C29 | The R65C00, R65C21, and R65C29 have two enhanced CMOS 6502s in a single chip, and the R65C00 and R65C21 additionally contained 2 KB of mask-programmable ROM. |
|  | CM630 | A 1 MHz [Eastern Bloc](/wiki/Eastern_Bloc) clone of the 6502 and was used in the [Pravetz](/wiki/Pravetz_computers) 8A and 8C, Bulgarian clones of the [Apple II](/wiki/Apple_II). |
| MOS | [7501](/wiki/MOS_Technology_7501) [8501](/wiki/MOS_Technology_8501) | 6510 (an enhanced 6502) variants, introduced in 1984. They extended the number of I/O port pins from 6 to 7, but omitted pins for non-maskable interrupt and clock output. Used in Commodore's [C-16](/wiki/Commodore_16), [C-116](/wiki/Commodore_16) and [Plus/4](/wiki/Commodore_Plus/4) computers. The main difference between 7501 and 8501 CPUs is that the 7501 was manufactured with the [HMOS](/wiki/HMOS)-1 process and the 8501 with HMOS-2. |
| MOS | [8500](/wiki/MOS_Technology_8500) | Introduced in 1985 as an [HMOS](/wiki/HMOS) version of the 6510 (which is in turn based on the 6502). Other than the process modification, the 8500 is virtually identical to the [NMOS](/wiki/NMOS_logic) version of the 6510. It replaced the 6510 in later versions of the [Commodore 64](/wiki/Commodore_64). |
| MOS | [8502](/wiki/MOS_Technology_8502) | Designed by MOS Technology and used in the [Commodore 128](/wiki/Commodore_128). Based on the MOS 6510 used in the Commodore 64, the 8502 was able to run at double clock rate of the 6510. The 8502 family also includes the MOS 7501, 8500 and 8501. |
| Hudson Soft | [HuC6280](/wiki/Hudson_Soft_HuC6280) | Japanese video game company [Hudson Soft](/wiki/Hudson_Soft)'s improved version of the WDC 65C02. Manufactured for them by [Seiko Epson](/wiki/Seiko_Epson) and [NEC](/wiki/NEC) for the [SuperGrafx](/wiki/SuperGrafx). The most notable product using the HuC6280 is NEC's TurboGrafx-16 video game console. |
| [VLSI](/wiki/VLSI_Technology) | VL65NC02 | VLSI licensed 65C02 variant was included in the [Atari Lynx](/wiki/Atari_Lynx)'s main system IC named Mikey. |

### 16-bit derivatives

The Western Design Center designed and, as of 2025, still produces the [WDC 65C816](/wiki/WDC_65C816)S processor, a 16-bit, static-core successor to the [65C02](/wiki/65C02). The W65C816S is a newer variant of the 65C816, which is the core of the [Apple IIGS](/wiki/Apple_IIGS) computer and is the basis of the [Ricoh 5A22](/wiki/Ricoh_5A22) processor that powers the [Super Nintendo Entertainment System](/wiki/Super_Nintendo_Entertainment_System). The W65C816S incorporates minor improvements over the 65C816 that make the newer chip not an exact hardware-compatible replacement for the earlier one. Among these improvements was conversion to a static core, which makes it possible to stop the clock in either phase without the registers losing data. Available through electronics distributors, as of March 2020, the W65C816S is officially rated for 14 MHz operation.

The Western Design Center also designed and produced the [65C802](/wiki/WDC_65C816), which was a 65C816 core with a 64-kilobyte address space in a 65(C)02 pin-compatible package. The 65C802 could be retrofitted to a 6502 board and would function as a 65C02 on power-up, operating in "emulation mode." As with the 65C816, a two-instruction sequence would switch the 65C802 to "native mode" operation, exposing its 16-bit [accumulator](/wiki/Accumulator_(computing)) and [index registers](/wiki/Index_register), and other 65C816 features. The 65C802 was not widely used and production ended.

## Bugs and quirks

The 6502 had several [bugs](/wiki/Hardware_bug) and quirks, which had to be accounted for when programming it:

- The earliest revisions of the 6502, such as those shipped with some [KIM-1](/wiki/KIM-1) computers, did not have a [ROR](/wiki/Circular_shift) (rotate right memory or accumulator) instruction. In these chips, the operation of the opcode that was later assigned to ROR is effectively an ASL (arithmetic shift left) instruction that does not affect the carry bit in the status register. Initially, MOS intentionally excluded ROR from the instruction set, deeming it not of enough value to justify its costs. In reaction to many customer inquiries, MOS promised in the second edition of the MCS6500 Programming Manual (document no. 6500-50A) that ROR would appear in 6502 chips starting in 1976. The vast majority of 6502 chips in existence today do feature the ROR instruction; these include all those CPUs originally installed in popular fully-assembled microcomputers such as the Apple II and Commodore 64 lines, all of which were manufactured after 1976.
- The [NMOS](/wiki/NMOS_logic) 6502 family has a variety of [undocumented instructions](/wiki/Illegal_opcode), which vary from one chip manufacturer to another. The 6502 instruction decoding is implemented in a [hardwired](/wiki/Hardwired_control) logic array (similar to a [programmable logic array](/wiki/Programmable_logic_array)) that is only defined for 151 of the 256 available [opcodes](/wiki/Opcode). The remaining 105 trigger strange and occasionally hard-to-predict actions, such as crashing the processor, performing two valid instructions consecutively, performing strange mixtures of two instructions, or simply doing nothing at all. Some hardware designers used the undefined opcodes to extend the 6502 instruction set by detecting when a certain undefined opcode is fetched and performing an extension operation externally to the processor while substituting a neutral (NOP-like) opcode to the 6502 in order to make it idle while the external hardware handles the extension operation. Also, some programmers utilized this feature to extend the 6502 instruction set by providing functionality for the unimplemented opcodes with specially written software intercepted at the BRK instruction's 0xFFFE vector. All of the undefined opcodes have been replaced with [NOP](/wiki/NOP_(code)) instructions in the [65C02](/wiki/65C02), an enhanced [CMOS](/wiki/CMOS) version of the 6502, although with varying byte sizes and execution times. (Some of them actually perform memory read operations but then ignore the data.) In the [65C802/65C816](/wiki/WDC_65C816), all 256 opcodes perform defined operations.
- The 6502's [memory indirect jump](/wiki/Indirect_branch) instruction, `JMP (<address>)`, has a nonintuitive limitation which many users consider a defect. If `<address>` is [hex](/wiki/Hexadecimal) `xxFF` (i.e., any word ending in `FF`), the processor will not jump to the address stored in `xxFF` and `xxFF+1` as expected, but rather the one defined by `xxFF` and `xx00` (for example, `JMP ($10FF)` would jump to the address stored in `10FF` and `1000`, instead of the one stored in `10FF` and `1100`). This can be avoided simply by not placing any indirect jump target address across a page boundary, and the MOS Technology MCS6500 Programming Manual gives reason to believe that this was the intention of the designers of the 6502, in order to save space on the chip that would have been used to implement the more complex behavior of conditionally adding 1 clock cycle to propagate the carry when necessary. This ostensible defect continued through the entire NMOS line but was corrected in the CMOS derivatives.
- The NMOS 6502 indexed addressing across page boundaries will do an extra read of an invalid address in the page of the base address (to which the index is added). This characteristic may cause random issues by accessing hardware that acts on a read, such as clearing timer or IRQ flags, sending an I/O handshake, etc. The extra read can be predicted and managed to avoid such problems, but only with special care in both hardware and software design. This flaw continued through the entire NMOS line but was corrected in the CMOS derivatives, in which the processor does an extra read of the last instruction byte.
- The 6502 [read–modify–write](/wiki/Read%E2%80%93modify%E2%80%93write) instructions perform one read and two write cycles. First, the unmodified data that was read is written back, and then the modified data is written. This characteristic may cause issues by twice accessing hardware that acts on a write. This anomaly continued through the full NMOS line but was fixed in the CMOS derivatives, in which the processor does two reads and one write cycle. [Defensive programming](/wiki/Defensive_programming) practice will generally avoid this problem by not executing read/modify/write instructions on hardware registers.
- The N (result negative), V (sign bit overflow) and Z (result zero) [status flags](/wiki/Status_register) are generally meaningless when performing arithmetic operations while the processor is in [BCD](/wiki/Binary-coded_decimal) mode, as these flags are undefined in decimal mode and have been empirically shown to reflect the binary, not BCD, result. This limitation was removed in the CMOS derivatives, at the cost of one added clock cycle for an ADC or SBC instruction in decimal mode (except on the 65C816). Therefore, this feature may be used to distinguish a CMOS processor from an NMOS version (by relying on the undocumented behavior of the NMOS version).
- If the 6502 happens to be in BCD mode when a hardware interrupt occurs, it will not revert to binary mode. This characteristic could result in obscure bugs in the interrupt service routine (ISR) if it fails to clear BCD mode before performing any arithmetic operations. The 6502 programming manual thus requires each ISR to reset or set the D flag if it uses the ADC or SBC instruction, but occasionally a human programmer may mistakenly omit to do this, causing a bug. For example, the [Commodore 64](/wiki/Commodore_64)'s [KERNAL](/wiki/KERNAL) did not correctly handle this processor characteristic, requiring that [IRQs](/wiki/Interrupt_request) be disabled or re-vectored during BCD math operations. This issue was addressed in the CMOS derivatives also, by making reset and all interrupts automatically reset the D flag. (The change has the one disadvantage that it makes a [rare] program that operates continuously in decimal mode slightly longer and slower, as now every ISR must *set* the D flag before executing ADC or SBC.)
- The 6502 instruction set includes BRK (opcode `$00`), which is technically a [software interrupt](/wiki/Software_interrupt) (similar in spirit to the SWI mnemonic of the [Motorola 6800](/wiki/Motorola_6800) and [ARM](/wiki/ARM_architecture_family) processors). BRK is most often used to interrupt program execution and start a [machine language monitor](/wiki/Machine_code_monitor) for testing and debugging during software development. BRK could also be used to route program execution using a simple jump table (analogous to the manner in which the [Intel 8086](/wiki/Intel_8086) and derivatives handle software interrupts by number). However, if a maskable [hardware interrupt](/wiki/Hardware_interrupt) occurs when the processor is fetching a BRK instruction, the NMOS version of the processor will fail to execute BRK and instead proceed as if only the hardware interrupt had occurred. This fault—an unequivocal hardware bug—was corrected in the CMOS implementation of the processor, which first calls the ISR for the hardware interrupt and then executes the BRK instruction.
- When executing JSR (jump to subroutine) and RTS (return from subroutine) instructions, the return address pushed to the stack by JSR is that of the last byte of the JSR operand (that is, the most significant byte of the subroutine address), rather than the address of the following instruction. This is because the actual copy (from [program counter](/wiki/Program_counter) to [stack](/wiki/Stack_(abstract_data_type)) and then conversely) takes place before the automatic increment of the program counter that occurs at the end of every instruction. This characteristic would go unnoticed unless the code examined the return address in order to retrieve parameters in the code stream. It remains a characteristic of 6502 derivatives to this day. The original MCS6500 Programming Manual points it out and explains the reason: it saves one clock cycle in the JSR by not incrementing the PC before pushing it, while in the RET instruction, the deferred increment of the pulled PC is overlapped with other steps and adds no clock cycle. As designed, a JSR and RET take 12 clock cycles total; if the JSR pushed the incremented PC, the call and return would take 13 clock cycles. To do an indirect branch, an address-1 is loaded from a table, pushed onto the stack, and then RTS.
- The SBC instruction (Subtract Memory from Accumulator with Borrow) uses inverted carry as borrow. A zero carry flag is used to signal borrow from previous subtract. If a borrow is not desired, the carry bit must be set before the SBC instruction. This way the ALU subtract logic can reuse the add logic with just inverted second input which saves a lot of gates.
- The read access of the CPU can be delayed by setting the RDY pin to low temporarily. However, during write access, which can take up to three consecutive clock cycles for a BRK instruction, the CPU will stop only in the next read cycle. This quirk was corrected in the CMOS derivatives and also in the 6510 and its variants.

## See also

- [List of 6502 assemblers](/wiki/Comparison_of_assemblers#6502_assemblers)
- [MOS Technology 6502-based home computers](/wiki/List_of_home_computers_by_category#MOS_Technology_6502)
- [Transistor count](/wiki/Transistor_count)
- [Apple II accelerators](/wiki/Apple_II_accelerators)
- [cc65](/wiki/Cc65) – 6502 macro assembler and C compiler

## Notes

## References

### Citations

### Bibliography

- Peddle, Chuck (12 June 2014). ["Oral History of Chuck Peddle"](https://www.youtube.com/watch?v=enHF9lMseP8) (Interview). Interviewed by Doug Fairbairn and Stephen Diamond. [Archived](https://ghostarchive.org/varchive/youtube/20211118/enHF9lMseP8) from the original on 2021-11-18.
- Bagnall, Brian (2010). *Commodore, a company on the edge* (2nd ed.). Winnipeg, Manitoba: Variant Press. [ISBN](/wiki/ISBN_(identifier)) [978-0-9738649-6-0](/wiki/Special:BookSources/978-0-9738649-6-0).
- Bennett, Thomas; Ekiss, John; Lattin, William (Bill); Lavell, Jeff (28 March 2008). ["Motorola 6800 Oral History Panel"](https://archive.computerhistory.org/resources/access/text/2015/06/102702020-05-01-acc.pdf) (PDF) (Interview). Interviewed by David Laws. [Archived](https://web.archive.org/web/20210413223530/https://archive.computerhistory.org/resources/access/text/2015/06/102702020-05-01-acc.pdf) (PDF) from the original on 2021-04-13. Retrieved 2021-01-30.
- [Cushman, Robert H.](/wiki/Robert_H._Cushman) (September 20, 1975). ["2-1/2 Generation μP's -$10 Parts That Perform Like Low-End Mini's"](https://web.archive.org/web/20160424050556/http://www.swtpc.com/mholley/Microprocessors/EDN_Sep_20_1975_6502.pdf) (PDF). *EDN*. **20** (17). Boston: Cahners Publishing: 36–42. Archived from [the original](http://www.swtpc.com/mholley/Microprocessors/EDN_Sep_20_1975_6502.pdf) (PDF) on 24 April 2016.
- [Interview with William Mensch](https://web.archive.org/web/20120508024231/http://silicongenesis.stanford.edu/complete_listing.html) Stanford and the Silicon Valley Project, October 9, 1995. [Transcript](https://web.archive.org/web/20160304091031/http://silicongenesis.stanford.edu/transcripts/mensch.htm)

## Further reading

Datasheets and manuals

- *[6500 Series Datasheet](https://archive.org/details/mos_6500_mpu_preliminary_may_1976)*; MOS Technology; 12 pages; 1976.
- *[6500 Series Hardware Manual](http://bytecollector.com/archive/misc/6500-10A_MCS6500hwMan_Jan76.pdf) [Archived](https://web.archive.org/web/20110913045342/http://bytecollector.com/archive/misc/6500-10A_MCS6500hwMan_Jan76.pdf) 2011-09-13 at the [Wayback Machine](/wiki/Wayback_Machine)*; 2nd Ed; MOS Technology; 182 pages; 1976.
- *[6500 Series Programming Manual](http://bytecollector.com/archive/misc/6500-50A_MCS6500pgmManJan76.pdf) [Archived](https://web.archive.org/web/20110913045402/http://bytecollector.com/archive/misc/6500-50A_MCS6500pgmManJan76.pdf) 2011-09-13 at the [Wayback Machine](/wiki/Wayback_Machine)*; 2nd Ed; MOS Technology; 262 pages; 1976.

Books

- [Zaks, Rodnay](/wiki/Rodnay_Zaks) (1979). [*6502 Applications Book*](https://archive.org/details/6502_Applications_Book/). Berkeley, Calif: [Sybex](/wiki/Sybex). [ISBN](/wiki/ISBN_(identifier)) [978-0-89588-015-4](/wiki/Special:BookSources/978-0-89588-015-4).
- Leventhal, Lance A. (1979). [*6502 Assembly Language Programming*](https://archive.org/details/6502-assembly-language-programming/). Berkeley/Calif: [Osborne/McGraw-Hill](/wiki/Osborne/McGraw-Hill). [ISBN](/wiki/ISBN_(identifier)) [978-0-931988-27-1](/wiki/Special:BookSources/978-0-931988-27-1).
- Leventhal, Lance A.; Saville, Winthrop (1982). [*6502 Assembly Language Subroutines*](https://archive.org/details/6502_Assembly_Language_Subroutines/). Berkeley, Calif: [Osborne/McGraw-Hill](/wiki/Osborne/McGraw-Hill). [ISBN](/wiki/ISBN_(identifier)) [978-0-931988-59-2](/wiki/Special:BookSources/978-0-931988-59-2).
- [Zaks, Rodnay](/wiki/Rodnay_Zaks) (1980). [*6502 Games*](https://archive.org/details/6502GamesRodnayZaks/). Berkeley, Calif: [Sybex](/wiki/Sybex). [ISBN](/wiki/ISBN_(identifier)) [978-0-89588-022-2](/wiki/Special:BookSources/978-0-89588-022-2).
- Carr, Joseph J. (1984). [*6502 User's Manual*](https://archive.org/details/6502UsersManual/). Reston, Virginia: [Reston Publishing](/wiki/Reston_Publishing). [ISBN](/wiki/ISBN_(identifier)) [978-0-83597-002-0](/wiki/Special:BookSources/978-0-83597-002-0).
- [Zaks, Rodnay](/wiki/Rodnay_Zaks) (1982). [*Advanced 6502 programming*](https://archive.org/details/Advanced_6502_Programming/). Berkeley, Calif: [Sybex](/wiki/Sybex). [ISBN](/wiki/ISBN_(identifier)) [978-0-89588-089-5](/wiki/Special:BookSources/978-0-89588-089-5).
- Mansfield, Richard (1983). [*Machine Language for Beginners: Personal Computer Machine Language Programming For The Atari, VIC, Apple, Commodore 64, And PET/CBM Computers*](https://project64.c64.org/Software/ml-bgnr.pdf) (PDF). Greensboro, N.C: [Compute! Publications](/wiki/Compute!_Publications). [ISBN](/wiki/ISBN_(identifier)) [978-0-942386-11-0](/wiki/Special:BookSources/978-0-942386-11-0).
  - Also available at [AtariArchives.org](https://www.atariarchives.org/mlb/index.php)
- [Zaks, Rodnay](/wiki/Rodnay_Zaks) (1983). [*Programming the 6502*](https://archive.org/details/Programming_the_6502_OCR/) (4th ed.). Berkeley: [SYBEX](/wiki/SYBEX). [ISBN](/wiki/ISBN_(identifier)) [978-0-89588-135-9](/wiki/Special:BookSources/978-0-89588-135-9).
- Eyes, David; Lichty, Ron (1986). [*Programming the 65816 – Including the 6502, 65C02, and 65802*](https://archive.org/details/0893037893ProgrammingThe65816/). New York, N.Y: [Prentice Hall](/wiki/Prentice_Hall). [ISBN](/wiki/ISBN_(identifier)) [978-0-89303-789-5](/wiki/Special:BookSources/978-0-89303-789-5).
- Topaloğlu, Nurettin (2021). *Mikroişlemciler ve Assembly Dili* [*Microprocessors and Assembly Language*] (in Turkish) (7th ed.). Çankaya: Seçkin Yayıncılık. [ISBN](/wiki/ISBN_(identifier)) [978-975-02-6663-8](/wiki/Special:BookSources/978-975-02-6663-8).

Reference cards

- *6502 Microprocessor Instant Reference Card*; James Lewis; Micro Logic; 2 pages; 1980. [(archive)](http://www.atarimania.com/documents/6502%20(65xx)%20Microprocessor%20Instant%20Reference%20Card.jpg) [Archived](https://web.archive.org/web/20190904042615/http://www.atarimania.com/documents/6502%20(65xx)%20Microprocessor%20Instant%20Reference%20Card.jpg) 2019-09-04 at the [Wayback Machine](/wiki/Wayback_Machine)

## External links

- [6502.org – the 6502 microprocessor resource](http://www.6502.org/) [Archived](https://web.archive.org/web/20201129185700/http://www.6502.org/) 2020-11-29 at the [Wayback Machine](/wiki/Wayback_Machine) – repository
- [The Rise of MOS Technology & The 6502](https://web.archive.org/web/20181004202006/https://www.commodore.ca/history/company/mos/mos_technology.htm) – Commodore archive
- [650x information](http://www.cpu-collection.de/?tn=1&l0=cl&l1=650x) [Archived](https://web.archive.org/web/20200311235418/http://www.cpu-collection.de/?tn=1&l0=cl&l1=650x) 2020-03-11 at the [Wayback Machine](/wiki/Wayback_Machine) – Concise description, photos of MOS and second source chips; at cpu-collection.de
- [mdfs.net](https://web.archive.org/web/20090113222331/http://mdfs.net/Docs/Comp/6502/) – 6502 instruction set
- Clever, Eric. ["6502 – the first RISC µP"](https://web.archive.org/web/20120524112833/http://ericclever.com/6500/). Archived from [the original](http://ericclever.com/6500/) on 24 May 2012.
- Harrod, Dennette A. (October 1980). ["6502 Gets Microprogrammable Instructions"](https://web.archive.org/web/20060525053048/http://wiz-worx.com/resume/byte8010.htm). *[Byte](/wiki/Byte_(magazine))*. Vol. 5, no. 10. [McGraw Hill](/wiki/McGraw_Hill). pp. 282–285. [ISSN](/wiki/ISSN_(identifier)) [0360-5280](https://search.worldcat.org/issn/0360-5280). Archived from [the original](http://www.wiz-worx.com/resume/byte8010.htm) on 2006-05-25. Retrieved 2006-05-14.

Simulators, emulators

- [Online 6502 compatible assembler and emulator, written in JavaScript](http://6502asm.com/) [Archived](https://web.archive.org/web/20110208004832/http://6502asm.com/) 2011-02-08 at the [Wayback Machine](/wiki/Wayback_Machine)
- [List of 6502 software emulators](http://www.zophar.net/6502.html) [Archived](https://web.archive.org/web/20200919032922/http://www.zophar.net/6502.html) 2020-09-19 at the [Wayback Machine](/wiki/Wayback_Machine) – Zophar's Domain
- [6502 simulator for Windows](http://atarihq.com/danb/6502.shtml) [Archived](https://web.archive.org/web/20041204171239/http://atarihq.com/danb/6502.shtml) 2004-12-04 at the [Wayback Machine](/wiki/Wayback_Machine) – Atari Gaming Headquarters
- [Visual Transistor-level Simulation of 6502 CPU](http://www.visual6502.org/) [Archived](https://web.archive.org/web/20110314114737/http://www.visual6502.org/) 2011-03-14 at the [Wayback Machine](/wiki/Wayback_Machine)
- [MCL65 6502 CPU core, C code](https://github.com/MicroCoreLabs/Projects/tree/master/MCL65) on [GitHub](/wiki/GitHub) – MicroCore Labs

Boards

- [Grant's 7/8-chip 6502 board](http://searle.x10host.com/6502/Simple6502.html) [Archived](https://web.archive.org/web/20220606014503/http://searle.x10host.com/6502/Simple6502.html) 2022-06-06 at the [Wayback Machine](/wiki/Wayback_Machine)
- [6502 microprocessor training board](http://www.kswichit.com/6502/6502.html) [Archived](https://web.archive.org/web/20190714012420/http://www.kswichit.com/6502/6502.html) 2019-07-14 at the [Wayback Machine](/wiki/Wayback_Machine)
- [Build your own KIM-1 training board](http://www.6502.org/trainers/) [Archived](https://web.archive.org/web/20190714012420/http://www.6502.org/trainers/) 2019-07-14 at the [Wayback Machine](/wiki/Wayback_Machine) – see [KIM-1](/wiki/KIM-1)
- [6502 home computer](https://github.com/grappendorf/homecomputer-6502) on [GitHub](/wiki/GitHub)
- [PE6502 single board computer](http://putnamelectronics.com/products.html) [Archived](https://web.archive.org/web/20200503122709/http://putnamelectronics.com/products.html) 2020-05-03 at the [Wayback Machine](/wiki/Wayback_Machine)
- [BE6502 single board computer](https://github.com/tebl/BE6502-Build-a-65c02-computer) on [GitHub](/wiki/GitHub) – based on Ben Eater videos

FPGA

- [cpu6502\_tc 6502 CPU core – VHDL source code](https://opencores.org/projects/cpu6502_true_cycle) – OpenCores
- [ag\_6502 6502 CPU core – Verilog source code](https://opencores.org/projects/ag_6502) [Archived](https://web.archive.org/web/20200804093306/https://opencores.org/projects/ag_6502) 2020-08-04 at the [Wayback Machine](/wiki/Wayback_Machine) – OpenCores
- [M65C02 65C02 CPU core – Verilog source code](https://opencores.org/projects/m65c02) [Archived](https://web.archive.org/web/20200804103904/https://opencores.org/projects/m65c02) 2020-08-04 at the [Wayback Machine](/wiki/Wayback_Machine) – OpenCores
- [MCL65 6502 CPU core](https://github.com/MicroCoreLabs/Projects/tree/master/MCL65) on [GitHub](/wiki/GitHub) – Verilog – MicroCore Labs
