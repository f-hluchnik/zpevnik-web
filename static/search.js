/*
 * The search of the online songbook (templates/search.html).
 *
 * The index (static/search-index.json, written by build.py) is loaded when the
 * field is first used, not with the other pages. A query is split into words,
 * and a song is found when every word is the beginning of a word in its title,
 * other titles, artists or lyrics, ignoring case and diacritics ("jede" finds
 * "jede" and "jedeme", not "pojedeme"). Titles come before artists, those
 * before lyrics, and a line of lyrics with all the words together before
 * words found apart; within each, the songs stay in the order of the book.
 * The results come in two groups, so that it is clear why a song was found:
 * the title or the artist, and the lyrics only. A song is in one group only,
 * the one it matches best.
 *
 * The query is kept in the address (?q=), so that the back button of the
 * browser returns from a song to the results.
 */
(function () {
  "use strict";

  var MIN_QUERY_LENGTH = 2;
  var LYRICS_SHOWN = 10; // of the group of the lyrics, until the reader asks for all
  var QUERY_PARAMETER = "q";

  // How well a song matches: the lower, the better.
  var RANK_TITLE = 0;
  var RANK_TITLES = 1;
  var RANK_ARTIST = 2;
  var RANK_PHRASE = 3; // the words together in one line of the lyrics
  var RANK_LYRICS = 4; // the words in the lyrics, apart

  // The groups of the results, in the order shown.
  var GROUPS = [
    {
      title: "V názvu nebo u interpreta",
      includes: function (rank) { return rank <= RANK_ARTIST; },
      shown: Infinity
    },
    {
      title: "V textu",
      includes: function (rank) { return rank >= RANK_PHRASE; },
      shown: LYRICS_SHOWN
    }
  ];

  var form = document.querySelector(".search");
  if (!form) {
    return;
  }
  var field = form.querySelector(".search-field");
  var status = document.querySelector(".search-status");
  var results = document.querySelector(".search-results");
  var indexUrl = form.dataset.indexUrl;
  var songbookPath = form.dataset.songbookPath;

  var songs = null; // the prepared index, once loaded
  var loading = null; // the request for it, while loading

  var SPACE = " ";

  /* "Čerešně" and "ceresne" are the same word. */
  function fold(text) {
    return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  }

  /* The words of a text, folded and one space apart ("Ain’t" is "ain t"), and a
     space before the first. A word starts where SPACE + word is found, and such
     texts can be joined by writing one after the other. */
  function words(text) {
    return SPACE + fold(text).replace(/[^\p{L}\p{N}]+/gu, SPACE).trim();
  }

  function startsWord(text, word) {
    return text.indexOf(SPACE + word) !== -1;
  }

  function prepare(entries) {
    return entries.map(function (entry) {
      var lines = entry.lyrics.split("\n");
      return {
        entry: entry,
        lines: lines,
        title: words(entry.title),
        titles: words([entry.title].concat(entry.altTitles).join(SPACE)),
        artists: words(entry.artists.join(SPACE)),
        wordLines: lines.map(words)
      };
    });
  }

  function loadIndex() {
    if (!loading) {
      loading = fetch(indexUrl)
        .then(function (response) {
          if (!response.ok) {
            throw new Error(response.status);
          }
          return response.json();
        })
        .then(function (entries) {
          songs = prepare(entries);
        })
        .catch(function (error) {
          loading = null; // try again at the next use
          throw error;
        });
    }
    return loading;
  }

  function startsAll(text, queryWords) {
    return queryWords.every(function (word) {
      return startsWord(text, word);
    });
  }

  /* The rank of a song for these words, or null if it does not match. */
  function rank(song, queryWords) {
    if (startsAll(song.title, queryWords)) {
      return RANK_TITLE;
    }
    if (startsAll(song.titles, queryWords)) {
      return RANK_TITLES;
    }
    if (startsAll(song.titles + song.artists, queryWords)) {
      return RANK_ARTIST;
    }
    if (!startsAll(song.titles + song.artists + song.wordLines.join(""), queryWords)) {
      return null;
    }
    return lineIndexOf(song, queryWords) !== -1 ? RANK_PHRASE : RANK_LYRICS;
  }

  function search(queryWords) {
    var found = [];
    songs.forEach(function (song, position) {
      var songRank = rank(song, queryWords);
      if (songRank !== null) {
        found.push({ song: song, rank: songRank, position: position });
      }
    });
    return found.sort(function (a, b) {
      return a.rank - b.rank || a.position - b.position;
    });
  }

  /* The first line of the lyrics where the words stand together, in this
     order, or -1. */
  function lineIndexOf(song, queryWords) {
    var phrase = queryWords.join(SPACE);
    return song.wordLines.findIndex(function (line) { return startsWord(line, phrase); });
  }

  /* The line of the lyrics that shows why a song was found: the one with the
     words together, else the first with one of them. */
  function matchingLine(song, queryWords) {
    var index = lineIndexOf(song, queryWords);
    for (var i = 0; index === -1 && i < queryWords.length; i += 1) {
      index = lineIndexOf(song, [queryWords[i]]);
    }
    return index === -1 ? null : song.lines[index];
  }

  /* An other title of the song with one of the words. */
  function matchingOtherTitle(song, queryWords) {
    var found = song.entry.altTitles.filter(function (title) {
      var titleWords = words(title);
      return queryWords.some(function (word) { return startsWord(titleWords, word); });
    });
    return found.length ? found[0] : null;
  }

  function element(tag, className, text) {
    var created = document.createElement(tag);
    created.className = className;
    created.textContent = text;
    return created;
  }

  /* A line of lyrics as a fragment, with the words that were looked for in bold:
     those that begin with one of the query words. */
  function highlightedLine(line, queryWords) {
    var fragment = document.createDocumentFragment();
    var wordPattern = /[\p{L}\p{N}\p{M}]+/gu;
    var end = 0;
    var found;
    while ((found = wordPattern.exec(line)) !== null) {
      var folded = fold(found[0]);
      if (queryWords.some(function (word) { return folded.indexOf(word) === 0; })) {
        fragment.appendChild(document.createTextNode(line.slice(end, found.index)));
        var bold = document.createElement("strong");
        bold.textContent = found[0];
        fragment.appendChild(bold);
        end = found.index + found[0].length;
      }
    }
    fragment.appendChild(document.createTextNode(line.slice(end)));
    return fragment;
  }

  function resultItem(match, queryWords) {
    var entry = match.song.entry;
    var item = document.createElement("li");
    var link = document.createElement("a");
    link.href = songbookPath + entry.id + "/";
    link.appendChild(element("span", "result-title", entry.title));
    item.appendChild(link);
    if (entry.artists.length) {
      item.appendChild(element("span", "result-artists", entry.artists.join(" · ")));
    }
    var otherTitle = matchingOtherTitle(match.song, queryWords);
    if (otherTitle) {
      item.appendChild(element("span", "result-detail", "též: " + otherTitle));
    }
    if (match.rank >= RANK_PHRASE) {
      var line = matchingLine(match.song, queryWords);
      if (line) {
        var lineElement = element("span", "result-detail result-line", "");
        lineElement.appendChild(highlightedLine(line, queryWords));
        item.appendChild(lineElement);
      }
    }
    return item;
  }

  /* "Nalezeno 5 písniček", in the Czech form of the number. */
  function countText(count) {
    if (count === 1) {
      return "Nalezena 1 písnička";
    }
    return (count < 5 ? "Nalezeny " : "Nalezeno ") + count + (count < 5 ? " písničky" : " písniček");
  }

  function showStatus(text) {
    status.textContent = text;
  }

  /* One group of results: a heading with the number of songs, and the list.
     A long list is cut short, with a button for the rest. */
  function resultGroup(group, matches, queryWords) {
    var section = document.createElement("section");
    section.className = "result-group";
    var heading = element("h2", "result-heading", group.title);
    heading.appendChild(document.createTextNode(SPACE));
    heading.appendChild(element("span", "result-count", "(" + matches.length + ")"));
    var list = document.createElement("ul");
    var items = matches.map(function (match) { return resultItem(match, queryWords); });
    list.replaceChildren.apply(list, items.slice(0, group.shown));
    section.appendChild(heading);
    section.appendChild(list);
    if (items.length > group.shown) {
      var more = element("button", "result-more", "Zobrazit všech " + items.length);
      more.type = "button";
      more.addEventListener("click", function () {
        list.replaceChildren.apply(list, items);
        more.remove();
        items[group.shown].querySelector("a").focus(); // the first of those just shown
      });
      section.appendChild(more);
    }
    return section;
  }

  function showResults(found, queryWords) {
    var groups = [];
    GROUPS.forEach(function (group) {
      var matches = found.filter(function (match) { return group.includes(match.rank); });
      if (matches.length) {
        groups.push(resultGroup(group, matches, queryWords));
      }
    });
    results.replaceChildren.apply(results, groups);
    showStatus(found.length ? countText(found.length) : "Nic nenalezeno.");
  }

  function clearResults() {
    results.replaceChildren();
  }

  function splitWords(query) {
    return words(query).split(SPACE).filter(Boolean);
  }

  function rememberQuery(query) {
    var address = query ? "?" + QUERY_PARAMETER + "=" + encodeURIComponent(query) : location.pathname;
    history.replaceState(null, "", address);
  }

  function update() {
    var query = field.value.trim();
    rememberQuery(query);
    if (query.length < MIN_QUERY_LENGTH) {
      clearResults();
      showStatus(query ? "Napište alespoň dvě písmena." : "");
      return;
    }
    if (!songs) {
      showStatus("Načítám…");
      loadIndex().then(update, function () {
        showStatus("Hledání se nepodařilo načíst. Zkuste to prosím znovu.");
      });
      return;
    }
    var queryWords = splitWords(query);
    showResults(search(queryWords), queryWords);
  }

  field.addEventListener("focus", function () {
    loadIndex().catch(function () { /* shown when the reader types */ });
  });
  field.addEventListener("input", update);
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    field.blur(); // puts the keyboard of a phone away
  });

  // A field that is already focused (the page asks for it) is about to be used.
  if (document.activeElement === field) {
    loadIndex().catch(function () { /* shown when the reader types */ });
  }

  var initialQuery = new URLSearchParams(location.search).get(QUERY_PARAMETER);
  if (initialQuery) {
    field.value = initialQuery;
    update();
  }
})();
