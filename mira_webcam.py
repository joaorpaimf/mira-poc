"""
MIRA - Modelo de Inspecao e Resposta Autonoma
POC: verificacao de EPI (capacete + colete) pela webcam.

Uso:
    python mira_webcam.py                 # webcam padrao
    python mira_webcam.py --camera 1      # outra camera
    python mira_webcam.py --fonte video.mp4

Teclas:  Q = sair   |   S = salvar foto do frame atual   |   F = tela cheia
"""
import argparse
import csv
import os
import platform
import shutil
import threading
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

# Classes do modelo treinado
CAPACETE, SEM_CAPACETE, COLETE, SEM_COLETE, PESSOA = 0, 1, 2, 3, 4

# Cores (BGR)
VERDE = (60, 180, 75)
VERMELHO = (40, 40, 220)
AMARELO = (0, 200, 255)
CINZA = (160, 160, 160)
BRANCO = (255, 255, 255)
AZUL_MARINHO = (80, 30, 10)

COR_CLASSE = {
    CAPACETE: VERDE,
    COLETE: VERDE,
    SEM_CAPACETE: VERMELHO,
    SEM_COLETE: VERMELHO,
    PESSOA: CINZA,
}
NOME_TELA = {
    CAPACETE: "capacete",
    COLETE: "colete",
    SEM_CAPACETE: "SEM capacete",
    SEM_COLETE: "SEM colete",
    PESSOA: "pessoa",
}

TITULO = "MIRA - Verificacao de EPI"


def centro(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def dentro(ponto, caixa, folga=0.1):
    """Ponto dentro da caixa (com uma folga proporcional ao tamanho da caixa)."""
    x, y = ponto
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    return (caixa[0] - folga * w <= x <= caixa[2] + folga * w and
            caixa[1] - folga * h <= y <= caixa[3] + folga * h)


def avaliar_frame(deteccoes):
    """
    Recebe lista de (classe, conf, caixa) e decide o status do frame.
    Retorna (status, faltando, pessoas)
      status: "OK", "NAO_CONFORME" ou "SEM_PESSOA"
      faltando: set com "capacete"/"colete"
      pessoas: lista de (caixa, ok, faltando) para desenhar
    """
    pessoas = [d for d in deteccoes if d[0] == PESSOA]
    epis = [d for d in deteccoes if d[0] != PESSOA]

    # Na portaria a pessoa costuma ficar muito perto da camera e o
    # modelo pode nao achar a "pessoa" inteira. Nesse caso, avaliamos
    # o frame todo como se fosse uma pessoa so.
    if not pessoas:
        if not epis:
            return "SEM_PESSOA", set(), []
        pessoas = [(PESSOA, 1.0, None)]

    resultado = []
    faltando_geral = set()
    for _, _, caixa in pessoas:
        tem = {c for c, _, b in epis if caixa is None or dentro(centro(b), caixa)}
        faltando = set()
        if CAPACETE not in tem or SEM_CAPACETE in tem:
            faltando.add("capacete")
        if COLETE not in tem or SEM_COLETE in tem:
            faltando.add("colete")
        resultado.append((caixa, not faltando, faltando))
        faltando_geral |= faltando

    status = "OK" if not faltando_geral else "NAO_CONFORME"
    return status, faltando_geral, resultado


def desenhar_caixa(frame, caixa, cor, texto, espessura=2):
    x1, y1, x2, y2 = map(int, caixa)
    cv2.rectangle(frame, (x1, y1), (x2, y2), cor, espessura)
    (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    y_txt = max(y1, th + 8)
    cv2.rectangle(frame, (x1, y_txt - th - 8), (x1 + tw + 8, y_txt), cor, -1)
    cv2.putText(frame, texto, (x1 + 4, y_txt - 5), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, BRANCO, 1, cv2.LINE_AA)


def desenhar_painel(frame, status, faltando, fps, fps_ia):
    h, w = frame.shape[:2]
    if status == "OK":
        cor, texto = VERDE, "LIBERADO"
        detalhe = "Capacete e colete OK"
    elif status == "NAO_CONFORME":
        cor, texto = VERMELHO, "BLOQUEADO"
        detalhe = "Falta: " + ", ".join(sorted(faltando))
    elif status == "VERIFICANDO":
        cor, texto = AMARELO, "VERIFICANDO..."
        detalhe = "Fique parado de frente para a camera"
    else:
        cor, texto = CINZA, "AGUARDANDO"
        detalhe = "Posicione-se em frente a camera"

    # Barra superior com a marca
    cv2.rectangle(frame, (0, 0), (w, 36), AZUL_MARINHO, -1)
    cv2.putText(frame, "MIRA | Verificacao de EPI", (12, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, BRANCO, 2, cv2.LINE_AA)
    # FPS da tela e FPS do modelo (IA), que pode ser menor
    cv2.putText(frame, f"{fps:4.1f} FPS | IA {fps_ia:4.1f}", (w - 200, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, BRANCO, 1, cv2.LINE_AA)

    # Barra inferior com o status
    cv2.rectangle(frame, (0, h - 70), (w, h), cor, -1)
    cv2.putText(frame, texto, (16, h - 32), cv2.FONT_HERSHEY_SIMPLEX,
                1.1, BRANCO, 3, cv2.LINE_AA)
    cv2.putText(frame, detalhe, (18, h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, BRANCO, 1, cv2.LINE_AA)


def encaixar_na_tela(frame, largura, altura):
    """Aumenta o frame para o tamanho da tela sem distorcer (faixas pretas nas sobras)."""
    if largura <= 0 or altura <= 0:
        return frame
    h, w = frame.shape[:2]
    escala = min(largura / w, altura / h)
    nw, nh = int(w * escala), int(h * escala)
    tela = np.zeros((altura, largura, 3), dtype=frame.dtype)
    x, y = (largura - nw) // 2, (altura - nh) // 2
    tela[y:y + nh, x:x + nw] = cv2.resize(frame, (nw, nh))
    return tela


class Registro:
    """Salva cada verificacao em CSV + foto quando for nao conforme."""

    def __init__(self, pasta="registros"):
        self.pasta = pasta
        os.makedirs(os.path.join(pasta, "fotos"), exist_ok=True)
        self.csv = os.path.join(pasta, "verificacoes.csv")
        if not os.path.exists(self.csv):
            with open(self.csv, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["data_hora", "status", "faltando", "foto"])

    def salvar(self, status, faltando, frame):
        agora = datetime.now()
        foto = ""
        if status == "NAO_CONFORME":
            foto = os.path.join(self.pasta, "fotos",
                                agora.strftime("%Y%m%d_%H%M%S") + ".jpg")
            cv2.imwrite(foto, frame)
        with open(self.csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([agora.strftime("%Y-%m-%d %H:%M:%S"), status,
                                    "|".join(sorted(faltando)), foto])
        print(f"[{agora:%H:%M:%S}] {status} {', '.join(sorted(faltando))}")


def abrir_fonte(fonte):
    if fonte.isdigit():
        idx = int(fonte)
        # No Windows o backend DirectShow abre a webcam bem mais rapido.
        # Em 1280x720 o DirectShow so entrega YUY2 a 10 FPS; em 848x480
        # (16:9, preenche a tela cheia) chega a 30 FPS. O modelo roda em
        # 480px, entao nao perde deteccao.
        if platform.system() == "Windows":
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 848)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
    else:
        cap = cv2.VideoCapture(fonte)
    # Nao acumula frames atrasados no buffer
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def carregar_modelo(caminho, imgsz):
    """
    No CPU o OpenVINO roda a inferencia ~4x mais rapido que o PyTorch.
    Na primeira execucao exporta o .pt para OpenVINO (leva ~1 min) e depois
    reaproveita a pasta. Se nao der, segue com o .pt mesmo.
    """
    if not caminho.endswith(".pt"):
        return aquecer(YOLO(caminho, task="detect"), imgsz)
    pasta = caminho[:-3] + "_openvino_model"
    meta = os.path.join(pasta, "metadata.yaml")
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            imgsz_exportado = yaml.safe_load(f).get("imgsz")
        if imgsz_exportado != [imgsz, imgsz]:
            shutil.rmtree(pasta)  # exportado com outro --imgsz
    if not os.path.exists(pasta):
        try:
            print("Exportando modelo para OpenVINO (so na primeira vez)...")
            YOLO(caminho).export(format="openvino", imgsz=imgsz)
        except Exception as e:
            print("Sem OpenVINO, usando PyTorch (mais lento):", e)
            return aquecer(YOLO(caminho), imgsz)
    return aquecer(YOLO(pasta, task="detect"), imgsz)


def aquecer(modelo, imgsz):
    """A 1a inferencia carrega/compila o modelo (varios segundos). Faz antes
    de abrir a camera para o video nao comecar travado."""
    print("Carregando modelo...")
    modelo.predict(np.zeros((480, 640, 3), np.uint8), imgsz=imgsz, verbose=False)
    return modelo


class Verificador:
    """Roda o modelo num frame e estabiliza o status com os ultimos frames."""

    def __init__(self, modelo, conf, imgsz, janela):
        self.modelo = modelo
        self.conf = conf
        self.imgsz = imgsz
        self.registro = Registro()
        self.historico = deque(maxlen=janela)
        self.status_confirmado = "SEM_PESSOA"
        self.faltando_confirmado = set()

    def processar(self, frame):
        """Retorna (deteccoes, pessoas, painel, faltando_confirmado)."""
        res = self.modelo.predict(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        deteccoes = [(int(c), float(p), b.tolist()) for c, p, b in
                     zip(res.boxes.cls, res.boxes.conf, res.boxes.xyxy)]

        status, faltando, pessoas = avaliar_frame(deteccoes)
        historico = self.historico
        historico.append((status, frozenset(faltando)))

        # So muda o status quando a maioria dos ultimos frames concorda
        votos = [s for s, _ in historico]
        mais_comum = max(set(votos), key=votos.count)
        if votos.count(mais_comum) >= 0.7 * len(historico) and len(historico) == historico.maxlen:
            falt = [f for s, f in historico if s == mais_comum]
            novo_faltando = set(max(set(falt), key=falt.count))
            if mais_comum != self.status_confirmado or novo_faltando != self.faltando_confirmado:
                self.status_confirmado, self.faltando_confirmado = mais_comum, novo_faltando
                if self.status_confirmado != "SEM_PESSOA":
                    self.registro.salvar(self.status_confirmado, self.faltando_confirmado, frame)
        painel = self.status_confirmado
        if status != "SEM_PESSOA" and self.status_confirmado == "SEM_PESSOA":
            painel = "VERIFICANDO"
        return deteccoes, pessoas, painel, self.faltando_confirmado


class InferenciaEmThread:
    """
    Roda o Verificador numa thread, sempre no frame mais recente da camera.
    Assim a tela anda na velocidade da camera (30 FPS) mesmo que o modelo
    seja mais lento; as caixas mostradas sao as da ultima inferencia.
    """

    def __init__(self, verificador):
        self.verificador = verificador
        self.lock = threading.Lock()
        self.novo_frame = threading.Event()
        self.frame = None
        self.resultado = ([], [], "SEM_PESSOA", set())
        self.fps = 0.0
        self.rodando = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def enviar(self, frame):
        with self.lock:
            self.frame = frame
        self.novo_frame.set()

    def ultimo(self):
        with self.lock:
            return self.resultado, self.fps

    def parar(self):
        self.rodando = False
        self.novo_frame.set()
        self.thread.join()

    def _loop(self):
        t_ant = time.time()
        while self.rodando:
            self.novo_frame.wait()
            self.novo_frame.clear()
            with self.lock:
                frame, self.frame = self.frame, None
            if frame is None:
                continue
            resultado = self.verificador.processar(frame)
            agora = time.time()
            with self.lock:
                self.resultado = resultado
                self.fps = 0.9 * self.fps + 0.1 * (1 / max(agora - t_ant, 1e-6))
            t_ant = agora


def desenhar_deteccoes(frame, deteccoes, pessoas):
    for c, p, b in deteccoes:
        if c != PESSOA:
            desenhar_caixa(frame, b, COR_CLASSE[c], f"{NOME_TELA[c]} {p:.0%}")
    for caixa, ok_p, falt in pessoas:
        if caixa is not None:
            cor = VERDE if ok_p else VERMELHO
            txt = "OK" if ok_p else "falta: " + ", ".join(sorted(falt))
            desenhar_caixa(frame, caixa, cor, txt, 3)


def main():
    ap = argparse.ArgumentParser(description="MIRA - POC de verificacao de EPI")
    ap.add_argument("--modelo", default="mira_ppe.pt", help="arquivo do modelo")
    ap.add_argument("--camera", default="0", help="indice da webcam (0, 1, ...)")
    ap.add_argument("--fonte", default=None, help="video ou stream (ex.: RTSP de CFTV)")
    ap.add_argument("--conf", type=float, default=0.35, help="confianca minima")
    ap.add_argument("--imgsz", type=int, default=480,
                    help="tamanho da imagem no modelo (menor = mais rapido)")
    ap.add_argument("--janela", type=int, default=45,
                    help="frames usados para confirmar o status (evita piscar; 45 = 1,5 s a 30 FPS)")
    args = ap.parse_args()

    modelo = carregar_modelo(args.modelo, args.imgsz)
    fonte = args.fonte or args.camera
    cap = abrir_fonte(fonte)
    if not cap.isOpened():
        print("Nao consegui abrir a camera/fonte. Tente --camera 1")
        return

    verificador = Verificador(modelo, args.conf, args.imgsz, args.janela)
    # Arquivo de video roda frame a frame (senao a leitura dispara e pula
    # quase todos os frames). Webcam e RTSP usam a thread de inferencia.
    inferencia = None if os.path.isfile(fonte) else InferenciaEmThread(verificador)
    fps, t_ant = 0.0, time.time()

    cv2.namedWindow(TITULO, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(TITULO, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    tela_cheia = True

    print("MIRA rodando. Q para sair, S para salvar foto, F tela cheia.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if inferencia:
            inferencia.enviar(frame.copy())
            (deteccoes, pessoas, painel, faltando), fps_ia = inferencia.ultimo()
        else:
            deteccoes, pessoas, painel, faltando = verificador.processar(frame)

        desenhar_deteccoes(frame, deteccoes, pessoas)

        agora = time.time()
        fps = 0.9 * fps + 0.1 * (1 / max(agora - t_ant, 1e-6))
        t_ant = agora
        desenhar_painel(frame, painel, faltando, fps, fps_ia if inferencia else fps)

        try:
            _, _, largura, altura = cv2.getWindowImageRect(TITULO)
        except cv2.error:
            largura = altura = 0  # janela fechada no X; o imshow recria
        cv2.imshow(TITULO, encaixar_na_tela(frame, largura, altura))
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("q"):
            break
        if tecla == ord("s"):
            nome = datetime.now().strftime("captura_%Y%m%d_%H%M%S.jpg")
            cv2.imwrite(os.path.join(verificador.registro.pasta, nome), frame)
            print("Foto salva:", nome)
        if tecla == ord("f"):
            tela_cheia = not tela_cheia
            modo = cv2.WINDOW_FULLSCREEN if tela_cheia else cv2.WINDOW_NORMAL
            cv2.setWindowProperty(TITULO, cv2.WND_PROP_FULLSCREEN, modo)

    if inferencia:
        inferencia.parar()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
