# Fase 1 — Janela do vídeo em tela cheia

- **What to change:** `mira_webcam.py:340` (antes do loop, em `main()`) - criar a janela com `cv2.namedWindow(TITULO, cv2.WINDOW_NORMAL)` e ativar `cv2.setWindowProperty(TITULO, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)`. Tela cheia é o padrão. O título `"MIRA - Verificacao de EPI"` passa a ser uma constante `TITULO`.
  - **Why to change:** hoje `cv2.imshow` (`mira_webcam.py:361`) cria uma janela automática do tamanho do frame (640x480), que não pode ser redimensionada nem ficar em tela cheia.

- **What to change:** `mira_webcam.py` (nova função perto de `desenhar_painel`, linha ~141) - `encaixar_na_tela(frame, largura, altura)`: redimensiona mantendo a proporção 4:3 e completa com faixas pretas nas laterais. O tamanho vem de `cv2.getWindowImageRect(TITULO)` a cada frame; se vier inválido (≤0), exibe o frame sem alterar. Em `mira_webcam.py:361`, `imshow` passa a exibir o resultado dessa função.
  - **Why to change:** o backend Win32 do `opencv-python` estica a imagem para a proporção do monitor (16:9), achatando as pessoas. O redimensionamento vale só para exibir: `desenhar_painel`/`desenhar_deteccoes` continuam desenhando no frame 640x480, e a foto do `S` (`mira_webcam.py:367`) e o `Registro` continuam salvando o frame original.

- **What to change:** `mira_webcam.py:362-368` - tecla `F` alterna entre tela cheia e janela (`WINDOW_FULLSCREEN` / `WINDOW_NORMAL`).
  - **Why to change:** sem isso, em tela cheia não dá para ver o terminal (logs, erros) sem fechar o programa.

- **What to change:** `mira_webcam.py:342` - mensagem passa a ser `"MIRA rodando. Q para sair, S para salvar foto, F tela cheia."`.
  - **Why to change:** documentar a nova tecla para quem roda.

- **What to change:** `mira_webcam.py:10` - docstring de teclas ganha `|   F = tela cheia` (incluído na Fase 2 a pedido).
  - **Why to change:** a ajuda no topo do arquivo também lista as teclas.

- **What to change:** `CLAUDE.md:23` e `README.md:20` - acrescentar `F` alterna tela cheia.
  - **Why to change:** manter a documentação de teclas igual ao comportamento.

## What all this shit means

**Abrir ocupando o monitor inteiro.** Hoje o MIRA abre numa janelinha do tamanho de uma foto pequena, num canto da tela, e não dá para aumentar. Com a mudança, ele abre ocupando o monitor inteiro, como um vídeo em tela cheia. Na portaria, o operador e o trabalhador enxergam o LIBERADO/BLOQUEADO de longe, sem ter que chegar perto do monitor.

**Não deixar a imagem esticada.** A câmera filma num formato mais "quadrado", parecido com uma TV antiga, e o monitor é mais largo, como uma TV moderna. Se a imagem só fosse esticada para caber, as pessoas iam aparecer largas e baixinhas, como num espelho de parque de diversões. Por isso a imagem é aumentada sem deformar, e sobram duas faixas pretas nas laterais, como quando um filme antigo passa numa TV nova. Só a imagem da tela aumenta: as fotos que o MIRA guarda como registro continuam do mesmo tamanho de hoje, então nada muda no que fica arquivado.

**Tecla F para sair e voltar da tela cheia.** Com a tela toda ocupada, a janela preta de comandos (onde aparecem os avisos do programa) fica escondida atrás. A tecla F funciona como um interruptor: aperta uma vez e o MIRA vira janela de novo, aperta outra vez e ele volta a ocupar a tela toda. Assim dá para olhar os avisos sem desligar o sistema.

**Avisar da tecla nova.** Quando o MIRA liga, ele mostra uma frase com as teclas que dá para usar ("Q para sair, S para salvar foto"). A tecla F entra nessa frase, para quem estiver operando saber que ela existe.

**Atualizar o manual.** Os textos de instrução do projeto listam as teclas do MIRA. A tecla F entra ali também, para o manual não ficar desatualizado em relação ao programa.
