# Fase 1 — Webcam em 16:9 para preencher a tela sem faixas pretas

Contexto: na tela cheia (`Screenshot_3.png`) a imagem aparece inteira, mas com faixas pretas nas laterais, porque a webcam entrega 640x480 (4:3) e o monitor é 1920x1080 (16:9). Teste nesta webcam com DirectShow: 640x360, 848x480 e 960x540 saem a 30 FPS; 1280x720 continua a 10 FPS.

- **What to change:** `mira_webcam.py:191-192` - pedir 848x480 à webcam em vez de 640x480.
  - **Why to change:** 848x480 tem a proporção do monitor (16:9) e sai a 30 FPS nesta webcam. Assim `encaixar_na_tela` preenche a tela inteira sem faixas e sem distorcer. A altura continua 480, então o custo de exibição quase não muda, e a inferência continua em `--imgsz 480`.

- **What to change:** `mira_webcam.py:185-186` - comentário passa a citar 848x480 (16:9, 30 FPS) em vez de 640x480.
  - **Why to change:** manter o comentário igual ao código.

- **What to change:** `CLAUDE.md:32` - trocar "640x480 a 30 FPS" por "848x480 (16:9, preenche a tela cheia) a 30 FPS".
  - **Why to change:** o CLAUDE.md documenta a resolução da webcam.

## What all this shit means

**Por que ficou com faixas pretas.** A imagem não foi cortada: tudo o que a câmera filma está na tela. O que aparece é uma faixa preta de cada lado, porque a câmera filma num formato mais quadrado, como uma TV antiga, e o monitor é largo, como uma TV moderna. Para não achatar as pessoas, a imagem foi aumentada até a altura da tela e sobrou espaço dos lados.

**A solução.** Testei a webcam e ela também sabe filmar no formato largo, igual ao do monitor, com a mesma fluidez de hoje (30 imagens por segundo). Basta pedir esse formato para ela. Aí a imagem encaixa certinho na tela, de ponta a ponta, sem faixas pretas e sem deformar ninguém.

**Efeitos para quem usa.** Na portaria, a tela fica toda ocupada pelo vídeo. As fotos guardadas como registro passam a ser mais largas, no mesmo formato da tela. Pode acontecer de a câmera mostrar um pouco mais dos lados do que hoje: nesse caso, quem passa aparece um pouquinho menor, mas quem está de frente para a câmera, perto, continua sendo visto normalmente. Em vídeos gravados ou câmeras de segurança com outro formato, as faixas pretas ainda podem aparecer, porque o formato dessas imagens não depende do MIRA.

**Atualizar as anotações.** As anotações do projeto dizem que a câmera filma no formato antigo. Elas passam a dizer o formato novo, para quem mexer depois não voltar ao formato errado sem querer.
