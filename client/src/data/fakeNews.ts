export interface FakeNewsItem {
  id: string;
  claim: string;
  excerpt: string;
  category: "conflict-misinformation" | "disaster-misinformation" | "celebrity-hoax" | "science-myth" | "scam-deepfake";
  sourceName: string;
  sourceUrl: string;
  dateFlagged: string;
}

export const fakeNewsItems: FakeNewsItem[] = [
  {
    id: "yemen-port-blaze",
    claim: "Video shows a new attack on a Saudi oil facility",
    excerpt: "The footage actually shows an old fire at a Yemeni port, unrelated to any recent attack on Saudi oil infrastructure.",
    category: "conflict-misinformation",
    sourceName: "Reuters Fact Check",
    sourceUrl: "https://www.reuters.com/fact-check/video-shows-old-yemen-port-blaze-not-attack-saudi-oil-facility-2026-03-13/",
    dateFlagged: "2026-03-13",
  },
  {
    id: "riyadh-embassy-strike",
    claim: "Video shows an Iranian strike on the US embassy in Riyadh",
    excerpt: "The clip actually shows an unrelated roadway fire, not a strike on the US embassy.",
    category: "conflict-misinformation",
    sourceName: "Reuters Fact Check",
    sourceUrl: "https://www.reuters.com/fact-check/roadway-fire-video-does-not-show-iranian-strike-riyadh-us-embassy-2026-03-12/",
    dateFlagged: "2026-03-12",
  },
  {
    id: "birmingham-councillor-fight",
    claim: "Video shows a fight among councillors in Birmingham, UK",
    excerpt: "The footage actually shows a courtroom fight in Pakistan, unrelated to UK local politics.",
    category: "conflict-misinformation",
    sourceName: "Reuters Fact Check",
    sourceUrl: "https://www.reuters.com/fact-check/video-shows-fight-pakistan-court-not-among-councillors-birmingham-2026-03-11/",
    dateFlagged: "2026-03-11",
  },
  {
    id: "japan-earthquake-old-photo",
    claim: "Photos show damage from a new March 2022 Fukushima earthquake",
    excerpt: "Several outlets used photos that actually date back to a previous Fukushima earthquake in February 2021.",
    category: "disaster-misinformation",
    sourceName: "The Quint (WebQoof)",
    sourceUrl: "https://www.thequint.com/news/webqoof/earthquake-image-from-2021-used-in-2022-fact-check",
    dateFlagged: "2022-03-17",
  },
  {
    id: "indonesia-flood-old-photo",
    claim: "Photo shows recent flood and landslide damage in Sumatra, Aceh, and Papua",
    excerpt: "The widely shared photo is actually from March 2024 floods in Padang, West Sumatra — not the more recent events it was captioned with.",
    category: "disaster-misinformation",
    sourceName: "Dismislab",
    sourceUrl: "https://en.dismislab.com/factcheck-indonesia-old-flood-image/",
    dateFlagged: "2025-12-07",
  },
  {
    id: "typhoon-rolly-old-photo",
    claim: "Photos show Bicol region devastation from Typhoon Rolly (Goni)",
    excerpt: "The photos are actually from Reuters' 2013 coverage of Super Typhoon Haiyan (Yolanda) in Tacloban, Leyte — seven years earlier and a different typhoon.",
    category: "disaster-misinformation",
    sourceName: "VERA Files",
    sourceUrl: "https://verafiles.org/?p=63595",
    dateFlagged: "2020-11-01",
  },
  {
    id: "chuck-norris-death-hoax",
    claim: "Chuck Norris has died",
    excerpt: "A viral YouTube video claimed the actor had passed away. No credible news outlet reported his death; the claim was a hoax.",
    category: "celebrity-hoax",
    sourceName: "Snopes",
    sourceUrl: "https://www.snopes.com/fact-check/chuck-norris-is-not-dead/",
    dateFlagged: "2023-11-01",
  },
  {
    id: "dick-van-dyke-death-hoax",
    claim: "Dick Van Dyke has died",
    excerpt: "A Facebook post falsely claimed the actor had died shortly before his real 97th birthday. He was alive and well.",
    category: "celebrity-hoax",
    sourceName: "Snopes",
    sourceUrl: "https://www.snopes.com/fact-check/dick-van-dyke-not-dead",
    dateFlagged: "2022-12-01",
  },
  {
    id: "elon-musk-crypto-deepfake",
    claim: "Elon Musk announced a Bitcoin and Ethereum giveaway",
    excerpt: "The video is an AI deepfake — Musk's face and voice were digitally manipulated to promote a fraudulent crypto giveaway site.",
    category: "scam-deepfake",
    sourceName: "The Quint (WebQoof)",
    sourceUrl: "https://www.thequint.com/news/webqoof/elon-musk-bitcoin-ethereum-giveaway-deepfake-fact-check",
    dateFlagged: "evergreen",
  },
  {
    id: "great-wall-visible-from-space",
    claim: "The Great Wall of China is visible from space with the naked eye",
    excerpt: "NASA and multiple astronauts — including China's own first astronaut, Yang Liwei — confirm the Wall is not visible to the naked eye from orbit; its ~6-meter width is below the threshold of naked-eye resolution at that distance.",
    category: "science-myth",
    sourceName: "Snopes",
    sourceUrl: "https://www.snopes.com/science/greatwal.htm",
    dateFlagged: "evergreen",
  },
  {
    id: "ten-percent-brain-myth",
    claim: "Humans only use 10% of their brains",
    excerpt: "Brain imaging (fMRI/PET) shows the entire brain is active across a given day; damage to any region, not just 90% of it, causes impairment.",
    category: "science-myth",
    sourceName: "Snopes",
    sourceUrl: "https://www.snopes.com/science/stats/10percnt.htm",
    dateFlagged: "evergreen",
  },
  {
    id: "goldfish-three-second-memory",
    claim: "Goldfish only have a 3-second memory",
    excerpt: "Goldfish can be trained to navigate mazes and recall learned behaviors weeks to months later — far beyond three seconds.",
    category: "science-myth",
    sourceName: "Live Science",
    sourceUrl: "https://livescience.com/goldfish-memory.html",
    dateFlagged: "evergreen",
  },
];
