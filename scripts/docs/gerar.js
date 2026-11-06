const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, BorderStyle, PageOrientation, LevelFormat, Footer, Header,
  PageNumber, PageBreak, TableLayoutType, VerticalAlign, ExternalHyperlink,
} = require('docx');
const { semanas, marcos, riscos } = require('./dados');

const SAIDA = process.argv[2];
const ULTIMA = [...semanas].reverse().find((s) => s.status === 'Concluída');
const REPO = 'https://github.com/AndreeSpecht/GalviTracks';

// Verificação: todas as datas precisam ser sextas-feiras
semanas.forEach((s) => {
  const [d, m, a] = s.data.split('/').map(Number);
  const dia = new Date(Date.UTC(a, m - 1, d)).getUTCDay();
  if (dia !== 5) throw new Error(`Semana ${s.n} (${s.data}) não é sexta-feira`);
});

const AZUL = '1F3864';
const AZUL_CLARO = 'D9E2F3';
const VERDE = 'E2EFD9';
const CINZA = 'F2F2F2';
const FONTE = 'Calibri';

const borda = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
const bordas = { top: borda, bottom: borda, left: borda, right: borda };

const p = (texto, opts = {}) => new Paragraph({
  spacing: { after: 120, line: 276 },
  alignment: opts.align || AlignmentType.JUSTIFIED,
  ...opts.para,
  children: Array.isArray(texto) ? texto : [new TextRun({ text: texto, ...opts.run })],
});
const t = (text, o = {}) => new TextRun({ text, ...o });
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(text)] });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(text)] });
const bullet = (children, nivel = 0) => new Paragraph({
  numbering: { reference: 'marcadores', level: nivel },
  spacing: { after: 60 },
  children: Array.isArray(children) ? children : [t(children)],
});

function celula(texto, largura, o = {}) {
  const linhas = Array.isArray(texto) ? texto : [texto];
  return new TableCell({
    width: { size: largura, type: WidthType.DXA },
    borders: bordas,
    verticalAlign: VerticalAlign.CENTER,
    shading: o.fundo ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fundo } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: linhas.map((l) => new Paragraph({
      alignment: o.align || AlignmentType.LEFT,
      children: [t(l, { bold: o.bold, color: o.cor, size: o.size || 18 })],
    })),
  });
}

function tabela(larguras, cabecalho, linhas, opts = {}) {
  const total = larguras.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: larguras,
    layout: TableLayoutType.FIXED,
    rows: [
      new TableRow({
        tableHeader: true,
        children: cabecalho.map((c, i) => celula(c, larguras[i], { bold: true, cor: 'FFFFFF', fundo: AZUL, align: AlignmentType.CENTER })),
      }),
      ...linhas.map((linha, r) => new TableRow({
        cantSplit: true,
        children: linha.map((c, i) => celula(c, larguras[i], {
          fundo: opts.fundoLinha ? opts.fundoLinha(linha, r) : (r % 2 ? CINZA : undefined),
          align: opts.centro && opts.centro.includes(i) ? AlignmentType.CENTER : AlignmentType.LEFT,
          bold: opts.negrito && opts.negrito.includes(i),
        })),
      })),
    ],
  });
}

const fundoStatus = (linha) => (String(linha[linha.length - 1]).startsWith('Conclu') ? VERDE : undefined);

// ---------- Capa ----------
const capa = [
  new Paragraph({ spacing: { before: 1800 }, alignment: AlignmentType.CENTER, children: [t('GALVITECH LTDA', { bold: true, size: 28, color: AZUL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 800 }, children: [t('Centro Universitário Católica de Santa Catarina · Engenharia de Software', { size: 22, color: '595959' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [t('Cronograma de Entregas', { bold: true, size: 56, color: AZUL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [t('Sistema de Rastreamento em Tempo Real de Motoboys', { size: 32 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1400 }, children: [t('Desenvolvido pela Galvitech · Implantação na Radar Auto Peças', { size: 24, italics: true, color: '595959' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [t('Trabalho de Conclusão de Curso · 8º período, semestre final (2026/2)', { size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [t('Entregas semanais às sextas-feiras · 07/08/2026 a 04/12/2026', { size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600 }, children: [t('Autor: ', { bold: true, size: 22 }), t('André Gustavo Specht', { size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [t('Professora: ', { bold: true, size: 22 }), t('Prof.ª Jessica Aline Karsten', { size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600 }, children: [t(`Jaraguá do Sul/SC · Versão do documento: ${ULTIMA.data} (entrega da semana ${ULTIMA.n})`, { size: 20, color: '595959' })] }),
];

// ---------- Corpo (retrato) ----------
const corpo = [
  h1('1. O projeto'),
  h2('1.1 Contexto'),
  p('A Radar Auto Peças, de Jaraguá do Sul/SC, faz grande parte das suas vendas com entrega por motoboy. Até então o despacho era manual: não havia rastreamento em tempo real dos entregadores, nem cálculo de rotas otimizadas, nem registro estruturado das viagens, e os motoboys informavam sua situação por telefone ou WhatsApp. A Galvitech Ltda, empresa de software de Jaraguá do Sul/SC, desenvolve o sistema de rastreamento para resolver esse problema.'),
  h2('1.2 Problema e pergunta de pesquisa'),
  p('Sem o sistema, a loja não consegue informar prazos confiáveis ao cliente final, tem dificuldade em alocar o motoboy mais próximo, não mantém histórico para avaliar desempenho e perde a rastreabilidade entre entregas e notas fiscais.'),
  p([t('Pergunta de pesquisa: ', { bold: true }), t('em que medida um sistema de rastreamento em tempo real de motoboys, construído com tecnologias abertas, é capaz de reduzir o tempo de planejamento de rotas e aumentar a eficiência e a rastreabilidade das entregas da Radar Auto Peças?', { italics: true })]),
  h2('1.3 Solução proposta'),
  p('Um sistema web independente, instalado no computador da loja e construído apenas com tecnologias abertas, sem custo de licenciamento:'),
  bullet([t('OwnTracks', { bold: true }), t(': app gratuito no celular do motoboy que envia a posição GPS ao servidor.')]),
  bullet([t('Flask + SQLite', { bold: true }), t(': backend em Python com API REST, regras de negócio e persistência.')]),
  bullet([t('OSRM + OpenStreetMap', { bold: true }), t(': cálculo de trajeto e tempo, com modo offline de contingência.')]),
  bullet([t('Leaflet.js', { bold: true }), t(': mapa interativo com motoboys, clientes e rotas.')]),
  p('As cinco funcionalidades principais são: (1) rastreamento GPS em tempo real, (2) gestão e otimização de rotas pela heurística do vizinho mais próximo, (3) cadastro de clientes, (4) histórico de viagens com o número da nota/pedido informado pelo operador e exportação Excel e (5) replay de trilha.', { para: { spacing: { before: 120, after: 120 } } }),
  p([t('Escopo: ', { bold: true }), t('o trabalho abrange somente o sistema de rastreamento descrito acima. Ele funciona de forma independente e não depende nem se integra a outros sistemas de gestão da loja. Os clientes são cadastrados no próprio sistema e o número da nota é digitado pelo operador na saída da entrega.')]),
  h2('1.4 Objetivos'),
  p([t('Geral: ', { bold: true }), t('desenvolver e avaliar um sistema de rastreamento em tempo real de motoboys para a Radar Auto Peças.')]),
  bullet('Levantar requisitos funcionais e não funcionais com a equipe da loja e os motoboys.'),
  bullet('Projetar a arquitetura do sistema e o modelo de dados.'),
  bullet('Implementar o rastreamento, as rotas, o cadastro de clientes, o histórico e o replay.'),
  bullet('Avaliar em ambiente real por cronometragem do planejamento de rotas e pelo questionário SUS.'),
  h2('1.5 Metodologia'),
  p('O trabalho segue a Design Science Research (Hevner et al., 2004): o artefato é construído em ciclos curtos e avaliado no ambiente real. Cada ciclo corresponde a uma entrega semanal, sempre às sextas-feiras, publicada no repositório público do GitHub.'),

  h1('2. Dinâmica das entregas semanais'),
  p('Toda sexta-feira há uma entrega verificável. Uma entrega é considerada concluída quando atende aos critérios abaixo:'),
  bullet('o código ou documento está no branch main do repositório, em commits com mensagens descritivas (padrão Conventional Commits);'),
  bullet('a suíte de testes automatizados passa no GitHub Actions (Windows e Ubuntu);'),
  bullet('a documentação em docs/ e o README estão atualizados;'),
  bullet('a entrega foi demonstrada à professora, quando aplicável.'),
  p([t('Repositório: ', { bold: true }), new ExternalHyperlink({ link: REPO, children: [t(REPO, { style: 'Hyperlink' })] })], { align: AlignmentType.LEFT }),
  p('As semanas 9 a 18 estão cadastradas como milestones no GitHub, com data de vencimento na sexta-feira correspondente, e as tarefas de cada semana aparecem como issues. Assim, o progresso pode ser acompanhado diretamente no repositório.'),
  p([t('Observação: ', { bold: true }), t('as entregas das semanas 1 a 8 foram consolidadas e publicadas no repositório em 25/09/2026. As datas desta tabela e a coluna Status podem ser editadas neste documento conforme o calendário acadêmico.', { italics: true })]),

  h1('3. Marcos do projeto'),
  tabela([900, 1500, 5126, 1500], ['Marco', 'Data', 'Descrição', 'Status'], marcos, { centro: [0, 1, 3], fundoLinha: fundoStatus }),
];

// ---------- Cronograma (paisagem) ----------
const LARG_PAISAGEM = [850, 1300, 1800, 5400, 3800, 1688]; // soma 14838 = largura útil A4 paisagem
const cronograma = [
  h1('4. Cronograma de entregas (sextas-feiras)'),
  p('Resumo das 18 entregas do semestre final. As linhas em verde já foram entregues.', { align: AlignmentType.LEFT }),
  tabela(
    LARG_PAISAGEM,
    ['Semana', 'Sexta-feira', 'Fase', 'Entrega', 'Evidência / artefato', 'Status'],
    semanas.map((s) => [String(s.n), s.data, s.fase, s.entrega, s.evidencia, s.status]),
    { centro: [0, 1, 5], fundoLinha: fundoStatus, negrito: [0] },
  ),
];

// ---------- Detalhamento (retrato) ----------
const detalhe = [h1('5. Detalhamento das entregas')];
semanas.forEach((s) => {
  detalhe.push(new Paragraph({
    heading: HeadingLevel.HEADING_3,
    keepNext: true,
    children: [t(`Semana ${String(s.n).padStart(2, '0')} · ${s.data} · ${s.fase}`)],
  }));
  detalhe.push(p([t('Entrega: ', { bold: true }), t(s.entrega)], { para: { keepNext: true }, align: AlignmentType.LEFT }));
  s.atividades.forEach((a) => detalhe.push(bullet(a)));
  detalhe.push(p([
    t('Evidência: ', { bold: true }), t(s.evidencia), t('     Status: ', { bold: true }),
    t(s.status, { bold: true, color: s.status === 'Concluída' ? '38761D' : 'B45F06' }),
  ], { align: AlignmentType.LEFT, para: { spacing: { after: 200 } } }));
});

const situacao = [
  h1(`6. Situação atual (entrega da semana ${ULTIMA.n}, ${ULTIMA.data})`),
  p('O repositório contém o sistema funcional, testado e documentado, pronto para rodar em qualquer computador com Python 3.10 ou superior:'),
  bullet([t('Código modular ', { bold: true }), t('no pacote radar_tracker (config, banco, frota, geo, roteamento, API e frontend).')]),
  bullet([t('Correções do protótipo: ', { bold: true }), t('rota duplicada, perda de nome/cor ao finalizar, XSS com nomes de clientes, busca sem codificação, filtro de datas inoperante e motoboys fixos no código.')]),
  bullet([t('Tratamento de GPS: ', { bold: true }), t('descarte por precisão, ordem temporal e saltos acima de 150 km/h.')]),
  bullet([t('Alertas de status (semana 9): ', { bold: true }), t('o painel avisa quando o motoboy fica sem sinal, parado mais de 10 min fora de um cliente ou com a bateria do celular abaixo de 20%.')]),
  bullet([t('Qualidade: ', { bold: true }), t('43 testes automatizados e integração contínua em Windows e Ubuntu.')]),
  bullet([t('Portabilidade: ', { bold: true }), t('instalar.bat/iniciar.bat (Windows) e instalar.sh/iniciar.sh (Linux/macOS), simulador de motoboy e dados de demonstração.')]),
  bullet([t('Documentação: ', { bold: true }), t('README, requisitos, arquitetura, API, banco de dados, instalação e histórico de desenvolvimento em docs/.')]),
  h2('Como executar'),
  p([t('Windows: ', { bold: true }), t('clonar o repositório, executar instalar.bat e depois iniciar.bat. O painel abre em http://127.0.0.1:5000.')], { align: AlignmentType.LEFT }),
  p([t('Linux/macOS: ', { bold: true }), t('./instalar.sh e ./iniciar.sh.')], { align: AlignmentType.LEFT }),
  p([t('Demonstração sem celular: ', { bold: true }), t('montar uma rota no painel e executar python scripts/simular_motoboy.py --tid 0.')], { align: AlignmentType.LEFT }),

  h1('7. Riscos e mitigação'),
  tabela([2500, 1400, 5126], ['Risco', 'Probabilidade', 'Mitigação'], riscos, { centro: [1] }),

  h1('8. Resultados esperados'),
  bullet('Redução mensurável do tempo médio de planejamento de rotas (cronometragem antes/depois).'),
  bullet('Dados operacionais estruturados: posição em tempo real, sequência otimizada de paradas e histórico de viagens.'),
  bullet('Rastreabilidade de cada entrega, com o número da nota/pedido registrado no histórico.'),
  bullet('Escore SUS na faixa "bom" (≥ 71) ou superior.'),
  bullet('Alternativa sem mensalidade às plataformas SaaS de entrega, hospedada na própria loja.'),

  h1('Referências'),
  ...[
    'BORGES, J. C. N. et al. Algoritmo para detecção de itinerários do transporte público usando dados de GPS dos ônibus. CoUrb 2023. SBC, 2023.',
    'BROOKE, J. SUS: a quick and dirty usability scale. In: Usability Evaluation in Industry. London: Taylor & Francis, 1996. p. 189–194.',
    'GOLDEN, B. L.; ASSAD, A. A. (Eds.). Vehicle Routing: Methods and Studies. Amsterdam: North-Holland, 1988.',
    'HEVNER, A. R. et al. Design science in information systems research. MIS Quarterly, v. 28, n. 1, p. 75–105, 2004.',
    'LUXEN, D.; VETTER, C. Real-time routing with OpenStreetMap data. ACM SIGSPATIAL GIS, 2011. p. 513–516.',
    'OWNTRACKS CONTRIBUTORS. OwnTracks booklet. Disponível em: https://owntracks.org/booklet/.',
    'LEAFLET CONTRIBUTORS. Leaflet: a JavaScript library for interactive maps. Disponível em: https://leafletjs.com/.',
  ].map((r) => p(r, { align: AlignmentType.LEFT, run: { size: 20 } })),
];

// ---------- Documento ----------
const cabecalho = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [t('Galvitech · Cronograma de Entregas · Rastreamento de Motoboys', { size: 16, color: '808080' })] })] });
const rodape = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t('Página ', { size: 16, color: '808080' }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '808080' })] })] });
const retrato = { page: { size: { width: 11906, height: 16838 }, margin: { top: 1300, bottom: 1200, left: 1440, right: 1440 } } };
const paisagem = { page: { size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE }, margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } };

const doc = new Document({
  creator: 'André Gustavo Specht',
  title: 'Cronograma de Entregas - Rastreamento de Motoboys',
  description: 'Cronograma semanal (sextas-feiras) do TCC - Sistema de rastreamento de motoboys',
  styles: {
    default: { document: { run: { font: FONTE, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, color: AZUL, font: FONTE },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0, keepNext: true,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: AZUL_CLARO, space: 4 } } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, color: '2F5496', font: FONTE },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 23, bold: true, color: '2F5496', font: FONTE },
        paragraph: { spacing: { before: 200, after: 60 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: {
    config: [{
      reference: 'marcadores',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 270 } } } }],
    }],
  },
  sections: [
    { properties: retrato, children: capa },
    { properties: retrato, headers: { default: cabecalho }, footers: { default: rodape }, children: corpo },
    { properties: paisagem, headers: { default: cabecalho }, footers: { default: rodape }, children: cronograma },
    { properties: retrato, headers: { default: cabecalho }, footers: { default: rodape }, children: [...detalhe, ...situacao] },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(SAIDA, buf);
  console.log('docx gerado:', SAIDA, buf.length, 'bytes');
});

// ---------- Versão Markdown ----------
if (process.argv[3]) {
  const md = [];
  md.push('# Cronograma de entregas', '');
  md.push('> Versão editável em Word: [`Cronograma_Entregas_TCC.docx`](Cronograma_Entregas_TCC.docx)', '');
  md.push('Entregas **toda sexta-feira** do 8º período, semestre final (2026/2), de 07/08/2026 a 04/12/2026. Uma entrega está concluída quando está no branch `main`, com testes passando no CI e documentação atualizada. As semanas 9 a 18 estão cadastradas como **milestones** no GitHub, com as tarefas em **issues**.', '');
  md.push('> As entregas das semanas 1 a 8 foram consolidadas e publicadas no repositório em 25/09/2026.', '');
  md.push('## Marcos', '', '| Marco | Data | Descrição | Status |', '|-------|------|-----------|--------|');
  marcos.forEach((m) => md.push(`| ${m[0]} | ${m[1]} | ${m[2]} | ${m[3] === 'Concluído' ? '✅ ' : '🔜 '}${m[3]} |`));
  md.push('', '## Entregas semanais', '', '| Sem. | Sexta-feira | Fase | Entrega | Evidência | Status |', '|:----:|:-----------:|------|---------|-----------|:------:|');
  semanas.forEach((s) => md.push(`| ${s.n} | ${s.data} | ${s.fase} | ${s.entrega} | ${s.evidencia} | ${s.status === 'Concluída' ? '✅' : '🔜'} ${s.status} |`));
  md.push('', '## Detalhamento', '');
  semanas.forEach((s) => {
    md.push(`### Semana ${String(s.n).padStart(2, '0')} · ${s.data} · ${s.fase}`, '', `**Entrega:** ${s.entrega}`, '');
    s.atividades.forEach((a) => md.push(`- ${a}`));
    md.push('', `**Evidência:** ${s.evidencia} · **Status:** ${s.status}`, '');
  });
  md.push('## Riscos e mitigação', '', '| Risco | Probabilidade | Mitigação |', '|-------|:-------------:|-----------|');
  riscos.forEach((r) => md.push(`| ${r[0]} | ${r[1]} | ${r[2]} |`));
  md.push('');
  fs.writeFileSync(process.argv[3], md.join('\n'), 'utf8');
  console.log('md gerado:', process.argv[3]);
}
