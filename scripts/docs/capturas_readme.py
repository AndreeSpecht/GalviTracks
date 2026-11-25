"""Capturas e GIF do README (docs/img), com a cena de scripts/docs/cena_demo.py rodando.

Requer: pip install playwright pillow (usa o Microsoft Edge instalado).
Uso: python scripts/docs/capturas_readme.py docs/img [login painel rota historico replay escuro celular demo]
O README usa os PNG reduzidos a 256 cores, para ficarem leves.
"""
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5098"
SAIDA = Path(sys.argv[1])
SAIDA.mkdir(parents=True, exist_ok=True)
SO = sys.argv[2:]  # nomes a gerar (vazio = todos)
erros = []


def quer(nome):
    return not SO or nome in SO


with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge", headless=True)

    def contexto(largura=1440, altura=900, tema="light", logado=True, **kw):
        ctx = nav.new_context(viewport={"width": largura, "height": altura}, color_scheme=tema,
                              device_scale_factor=1, locale="pt-BR", **kw)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: erros.append(str(e)))
        if logado:
            pg.goto(URL + "/login")
            pg.fill("input[name=usuario]", "andre")
            pg.fill("input[name=senha]", "demo-portfolio")
            pg.click("button[type=submit]")
            pg.wait_for_selector(".cartao")
            pg.wait_for_timeout(3000)
        return ctx, pg

    def cartao(pg, mid):
        pg.click(f".cartao[data-id='{mid}']")
        pg.wait_for_timeout(2500)

    if quer("login"):
        ctx, pg = contexto(logado=False)
        pg.goto(URL + "/login")
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(SAIDA / "login.png"))
        ctx.close()

    if quer("painel"):
        ctx, pg = contexto()
        cartao(pg, 0)
        pg.screenshot(path=str(SAIDA / "painel.png"))
        ctx.close()

    if quer("rota"):
        ctx, pg = contexto()
        cartao(pg, 2)
        pg.screenshot(path=str(SAIDA / "rota.png"))
        ctx.close()

    if quer("historico"):
        ctx, pg = contexto()
        pg.click("#btn-historico")
        pg.wait_for_timeout(2000)
        pg.screenshot(path=str(SAIDA / "historico.png"))
        ctx.close()

    if quer("replay"):
        ctx, pg = contexto()
        cartao(pg, 1)
        pg.click("button[title='Replay da trilha']")
        pg.wait_for_timeout(2500)
        pg.click(".replay-slider", position={"x": 300, "y": 5})
        pg.wait_for_timeout(1200)
        pg.screenshot(path=str(SAIDA / "replay.png"))
        ctx.close()

    if quer("escuro"):
        ctx, pg = contexto(tema="dark")
        cartao(pg, 3)
        pg.click("#btn-alertas")
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(SAIDA / "escuro.png"))
        ctx.close()

    if quer("celular"):
        ctx, pg = contexto(390, 844, is_mobile=True, has_touch=True)
        pg.screenshot(path=str(SAIDA / "celular.png"))
        ctx.close()

    if quer("demo"):
        # GIF: login, frota andando, despacho do Paulo e histórico
        ctx, pg = contexto(1280, 760, logado=False)
        quadros = []

        def gravar(segundos, intervalo=0.5):
            fim = time.monotonic() + segundos
            while time.monotonic() < fim:
                t0 = time.monotonic()
                quadros.append(Image.open(io.BytesIO(pg.screenshot(type="png"))).convert("RGB"))
                time.sleep(max(0, intervalo - (time.monotonic() - t0)))

        pg.goto(URL + "/login")
        pg.wait_for_timeout(500)
        gravar(1)
        pg.type("input[name=usuario]", "andre", delay=90)
        gravar(0.5)
        pg.type("input[name=senha]", "demo-portfolio", delay=40)
        gravar(0.5)
        pg.click("button[type=submit]")
        pg.wait_for_selector(".cartao")
        pg.wait_for_timeout(2500)
        gravar(5)
        pg.click(".cartao[data-id='2']")
        gravar(3)
        pg.click("#btn-otimizar")
        gravar(2)
        pg.type("#inp-nota", "456216", delay=120)
        gravar(1)
        pg.click("text=Sair para entrega")
        gravar(4)
        pg.click(".cartao[data-id='0']")
        gravar(4)
        pg.click("#btn-historico")
        gravar(3)
        ctx.close()
        largura = 960
        menores = [q.resize((largura, round(q.height * largura / q.width)), Image.LANCZOS) for q in quadros]
        pal = [m.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for m in menores]
        pal[0].save(SAIDA / "demo.gif", save_all=True, append_images=pal[1:], duration=500, loop=0, optimize=True)
        print("quadros:", len(quadros))

    nav.close()

print("\n".join(erros) if erros else "sem erros de JavaScript")
