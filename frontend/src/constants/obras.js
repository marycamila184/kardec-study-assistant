export const OBRAS = [
  {
    id: 'le',
    abbr: 'LE',
    shortLabel: 'Livro dos Espíritos',
    label: 'O Livro dos Espíritos',
    year: 'Paris, 1857 — Primeira obra da codificação',
    summary: 'Os fundamentos da doutrina: Deus, Espíritos, alma, reencarnação e leis morais. Base de todo o estudo espírita.',
    topics: [
      {
        title: 'Parte I — Das Causas Primárias',
        subtitle: 'Deus, os Espíritos e a criação',
        context: 'Kardec abre a obra com as perguntas mais fundamentais da existência humana. O que é Deus, quem são os Espíritos e qual é a origem e o propósito da criação.',
        items: ['O que é Deus? (Q.1)', 'Atributos da Divindade (Q.13)', 'Providência divina (Q.963)', 'O que são os Espíritos? (Q.76)', 'Origem dos Espíritos (Q.78)', 'Mundos habitados (Q.55)'],
      },
      {
        title: 'Parte II — Do Mundo Espiritual',
        subtitle: 'Alma, encarnação, reencarnação e vida após a morte',
        context: 'A parte mais extensa da obra. Trata da natureza da alma, do perispírito, do processo de encarnação e reencarnação, da vida entre as encarnações e do que acontece após a morte física.',
        // Q.167 (the purpose of reincarnation) and Q.100 (the spirit scale,
        // impure to pure) replaced Q.166 and Q.165, which landed on "how the
        // soul purifies" and on the duration of the post-mortem daze —
        // neighbouring subjects, but not the ones the label promises. The
        // number matters: extract_study_reference resolves it and it becomes
        // the "Da Obra" block, so a wrong one shows the reader a wrong passage.
        //
        // Q.97 then replaced Q.100 on 2026-08-04, keeping that same intent —
        // the scale, imperfect to pure — in 742 characters instead of 4423.
        // Q.100 is OBSERVAÇÕES PRELIMINARES: five paragraphs of method, on
        // Linnaeus and botanical classification, before the three orders
        // arrive. Q.97 asks the question and the answer IS the three orders.
        // Size is not a matter of taste here: measured over the 21 numbered
        // topic items, the median is ~500 characters and only Q.100 and
        // Q.1009 passed 4000 — and those two are the only ones a reader
        // reported coming back "não encontrei" from. See the note on Q.1006
        // in Parte IV.
        // The label follows the passage rather than the passage following the
        // label: Q.97 is about the orders of perfection, not about happy and
        // suffering Spirits, and a label promising the second while showing
        // the first is exactly the mismatch the paragraph above warns about.
        items: ['O que é a alma? (Q.134)', 'O perispírito (Q.93)', 'Por que nos encarnamos? (Q.132)', 'Reencarnação (Q.167)', 'Vida após a morte (Q.149)', 'A escala dos Espíritos (Q.97)'],
      },
      {
        title: 'Parte III — Das Leis Morais',
        subtitle: 'As leis divinas que regem a existência',
        context: 'Kardec apresenta as grandes leis naturais como expressão da vontade divina: adoração, trabalho, reprodução, conservação, destruição, sociedade, progresso, igualdade, liberdade, justiça e amor.',
        // Q.886 opens the meaning of charity inside DA LEI DE JUSTIÇA, DE AMOR
        // E DE CARIDADE (Q.873–892); Q.674 opens DA LEI DO TRABALHO (Q.674–685).
        // The previous numbers (614, 664) landed in DA LEI DIVINA OU NATURAL and
        // in DA LEI DE ADORAÇÃO — the latter on a question about praying for the
        // dead, which is the passage that came up when you clicked "the law of
        // work".
        items: ['A lei do amor e da caridade (Q.886)', 'A lei do trabalho (Q.674)', 'Livre-arbítrio (Q.843)', 'A lei da igualdade (Q.803)', 'Virtudes e vícios (Q.893)'],
      },
      {
        title: 'Parte IV — Das Esperanças e Consolações',
        subtitle: 'O destino do Espírito e a vida futura',
        context: 'A parte conclusiva responde às grandes angústias humanas: existem penas eternas? O que é o paraíso? Kardec apresenta uma visão de justiça divina baseada no progresso infinito.',
        // Q.967 ("what the happiness of good Spirits consists of") replaces
        // Q.920, which opens DAS PENAS E GOZOS **TERRESTRES** and asks whether
        // man can be happy ON EARTH — the opposite of what the label promises.
        //
        // Q.1006 replaced Q.1009 on 2026-08-04, and this one was about size,
        // not about aim. Both answer the label; Q.1009 took 11655 characters
        // to do it — 23x the median of these items, and 13x Q.1006 — because
        // it is not a question and answer at all but five dissertations
        // (Santo Agostinho, Lamennais, Platão, São Paulo) plus Kardec's
        // commentary. Q.1006 asks "poderão durar eternamente os sofrimentos
        // do Espírito?" and answers it in 892 characters, which is the whole
        // of what the label promises.
        //
        // The Da Obra block renders with `white-space: pre-wrap` and no
        // collapse, so an 11k-character item is 11k characters on screen
        // before the explanation starts. Reported by the reader as "muito
        // grande", and it is also one of the two items observed returning
        // "não encontrei" in production — see the note on Q.97 in Parte II.
        items: ['Penas eternas — sim ou não? (Q.1006)', 'O progresso dos Espíritos (Q.780)', 'Mundos superiores (Q.188)', 'A felicidade futura (Q.967)'],
      },
    ],
  },
  {
    id: 'lm',
    abbr: 'LM',
    shortLabel: 'Livro dos Médiuns',
    label: 'O Livro dos Médiuns',
    year: 'Paris, 1861 — Segunda obra da codificação',
    summary: 'Mediunidade, evocações, tipos de manifestações e como discernir os Espíritos.',
    topics: [
      {
        title: 'Parte I — Dos Agentes Mediúnicos',
        subtitle: 'Quem são os médiuns e os Espíritos',
        context: 'Kardec explica quem são os agentes das comunicações espíritas: de um lado os Espíritos, de outro os médiuns — suas faculdades, tipos e desenvolvimento.',
        // "Desenvolvimento mediúnico" is modern spiritist vocabulary that does
        // not appear in the work: semantic search retrieved NOTHING in the book
        // and nothing on the cross-book fallback, so the button answered "não
        // encontrei". The chapter is called "Da formação dos médiuns" (200–220).
        // The labels stay in Portuguese: each one IS the query, matched against
        // a Portuguese corpus.
        items: ['O que é mediunidade?', 'Tipos de médiuns', 'A formação dos médiuns', 'Espíritos bons e maus', 'Como se comunicam os Espíritos?'],
      },
      {
        title: 'Parte II — Das Manifestações Espíritas',
        subtitle: 'Os fenômenos e como estudá-los',
        context: 'Um guia rigoroso para compreender as manifestações físicas e intelectuais dos Espíritos.',
        // Kardec writes "manifestações INTELIGENTES", not "intelectuais" — the
        // chapter carries that name (items 65–71). With the wrong word the
        // button retrieved nothing and fell through to "não encontrei".
        items: ['Manifestações físicas', 'As manifestações inteligentes', 'Mesas girantes', 'A escrita mediúnica (psicografia)', 'Como verificar a autenticidade'],
      },
      {
        title: 'Parte III — Das Evocações',
        subtitle: 'Como, quando e por que evocar',
        context: 'Kardec explica as condições para evocar Espíritos com seriedade, os riscos da leviandade e como agir com Espíritos sofredores.',
        items: ['Condições para as evocações', 'Evocação de familiares', 'Espíritos sofredores', 'Riscos das evocações frívolas', 'Como lidar com obsessões'],
      },
    ],
  },
  {
    id: 'ese',
    abbr: 'ESE',
    shortLabel: 'Evangelho',
    label: 'O Evangelho Segundo o Espiritismo',
    year: 'Paris, 1864 — Terceira obra da codificação',
    summary: 'Comentários aos ensinamentos morais do Cristo à luz da doutrina espírita. A obra da prática: caridade, humildade, perdão e amor.',
    topics: [
      {
        title: 'Parte I — Os Fundamentos Morais',
        subtitle: 'Fé, razão e os ensinamentos de Jesus',
        context: 'Kardec interpreta os ensinamentos morais do Cristo à luz da doutrina espírita.',
        // Faith is chapter XIX (A FÉ TRANSPORTA MONTANHAS) and "Sede perfeitos"
        // is chapter XVII, which carries that title. II is "Meu reino não é
        // deste mundo" and IV is the being-born-again chapter.
        items: ['Fé e razão (cap. XIX)', 'Bem-aventuranças (cap. V)', 'O Cristo e a doutrina', 'Sede perfeitos (cap. XVII)'],
      },
      {
        title: 'Parte II — A Vida Moral na Prática',
        subtitle: 'Virtudes, vícios e o caminho do bem',
        context: 'A parte mais cotidiana da obra: caridade, humildade, perdão, tolerância.',
        // XI and XII were swapped: XI is "Amar o próximo como a si mesmo", XII
        // is "Amai os vossos inimigos". Forgiveness of offences is a section of
        // chapter X (Bem-aventurados os misericordiosos), and humility is
        // chapter VII ("O orgulho e a humildade"); XIV is "Honrai a vosso pai e
        // a vossa mãe".
        items: ['Amar os inimigos (cap. XII)', 'A caridade (cap. XIII)', 'A humildade (cap. VII)', 'O perdão das ofensas (cap. X)'],
      },
      {
        title: 'Parte III — Provas e Consolações',
        subtitle: 'Sofrimento, prece e esperança',
        context: 'Por que sofremos? Qual o valor das tribulações? Kardec responde com profundidade e conforto espiritual.',
        // Tribulations are chapter V ("Justiça das aflições", "Motivos de
        // resignação"); XVI is "Não se pode servir a Deus e a Mamon".
        // **There is no chapter XXX**: the work ends at XXVIII. Life after death
        // is chapter III, "Há muitas moradas na casa de meu pai", with the
        // sections on the states of the soul in erraticity.
        items: ['Tribulações (cap. V)', 'A prece e sua eficácia (cap. XXVII)', 'A morte e a vida (cap. III)', 'O livre-arbítrio'],
      },
    ],
  },
  {
    id: 'ci',
    abbr: 'CI',
    shortLabel: 'Céu e o Inferno',
    label: 'O Céu e o Inferno',
    year: 'Paris, 1865 — Quarta obra da codificação',
    summary: 'A doutrina das penas e recompensas futuras. Exemplos de vidas e mortes narrados pelos próprios Espíritos.',
    topics: [
      {
        title: 'Parte I — Doutrina',
        subtitle: 'O que são o Céu e o Inferno para o Espiritismo',
        context: 'Kardec confronta as doutrinas tradicionais do céu, inferno e purgatório com os princípios espíritas.',
        items: ['O que é o inferno espírita?', 'Existe o purgatório?', 'O paraíso na doutrina', 'Penas eternas — sim ou não?'],
      },
      {
        title: 'Parte II — Exemplos',
        subtitle: 'Narrativas reais de vidas e mortes',
        context: 'Relatos de Espíritos em diferentes condições após a morte — sofrendo, felizes, arrependidos, em progresso.',
        // "Morte repentina" retrieved nothing in this book and fell through,
        // via the cross-book fallback, to O Livro dos Espíritos — a different
        // work from the one the panel is showing. The chapter that covers it is
        // called "O passamento".
        //
        // "Suicídio e consequências" was removed 2026-08-05 for a cause no
        // relabelling can reach, and the difference is worth keeping straight.
        // Raw retrieval DOES find the material — 5 chunks at 0.409–0.442, all
        // in II PARTE · SUICIDAS — and filter_uncitable_chunks then drops every
        // one of them: that chapter is 104 chunks of spirit testimony with 0
        // numbered items, and no numbered item anywhere in this book mentions
        // suicide. So the chip promised a subject the book cannot offer in a
        // form the reader could look up, which is the opposite of what the
        // Da Obra separation exists to guarantee. "Suicidas", the chapter's own
        // title, comes back just as empty; the only phrasing that returned
        // anything was worse than the failure — one chunk of O PASSAMENTO, a
        // chapter about dying in general, not about suicide.
        items: ['Espíritos em sofrimento', 'Espíritos felizes', 'A perturbação depois da morte'],
      },
    ],
  },
  {
    id: 'gen',
    abbr: 'GEN',
    shortLabel: 'A Gênese',
    label: 'A Gênese',
    year: 'Paris, 1868 — Quinta obra da codificação',
    summary: 'Concilia ciência, filosofia e religião: a criação do universo, os milagres e a origem da vida segundo o Espiritismo.',
    topics: [
      {
        title: 'Parte I — Gênese Cosmogônica',
        subtitle: 'A criação do universo segundo o Espiritismo',
        context: 'Kardec aborda a criação do universo a partir de uma perspectiva que concilia ciência e espiritualidade.',
        items: ['A criação segundo o Espiritismo', 'A formação dos mundos', 'Anjos e demônios', 'Milagres e leis naturais'],
      },
      {
        title: 'Parte II — Gênese Biológica e Moral',
        subtitle: 'A origem do homem e da moral',
        context: 'A segunda parte trata da origem do homem físico e moral.',
        items: ['A origem do homem', 'Adão e Eva — interpretação espírita', 'Os milagres de Jesus explicados', 'Ressurreição e reencarnação'],
      },
    ],
  },
];
