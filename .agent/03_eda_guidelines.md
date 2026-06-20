# Directrices para Diseño de Circuitos Integrados (EDA)

- **Herramientas de Diseño (Open-Source):** The OpenROAD Project, Yosys (Síntesis), KLayout (Visualización y análisis), Magic.
- **Lenguajes Utilizados:** Verilog (RTL), TCL (Configuración de flujo OpenROAD y *constraints* SDC), Python (Scripts de análisis físico en KLayout).
- **Arquitectura de Hardware:** Fuerte enfoque en el ecosistema abierto RISC-V (ej. PicoRV32, Ibex) y el desarrollo de System-on-Chip (SoC) interconectados mediante buses estándar de la industria (AMBA: AXI, AHB, APB).
- **Flujo de Trabajo:** Orientado al lema *"No-Human-in-the-Loop"*, persiguiendo un flujo automatizado desde RTL hasta la obtención del archivo GDSII (Layout).
- **Fabricación y PDKs:** Trabajar bajo las reglas de Process Design Kits abiertos, como SkyWater 130nm (`sky130`).
- **Objetivos de Rendimiento:** Considerar siempre los desafíos del diseño físico, priorizando el *Timing Closure* (setup/hold), el área y el enrutado libre de violaciones DRC/LVS.