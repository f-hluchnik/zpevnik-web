/*
 * The search of the online songbook (templates/search.html).
 *
 * The index (static/search-index.json, written by build.py) is loaded when the
 * field is first used, not with the other pages. A query is split into words,
 * and a song is found when every word occurs in its title, other titles,
 * artists or lyrics, ignoring case and diacritics. Titles come before artists,
 * those before lyrics, and a line of lyrics with all the words together before
 * words found apart; within each, the songs stay in the order of the book.
 *
 * The query is kept in the address (?q=), so that the back button of the
 * browser returns from a song to the results.
 */
(function () {
  "use strict";

  var MIN_QUERY_LENGTH = 2;
  var MAX_RESULTS = 60;
  var QUERY_PARAMETER = "q";

  // How well a song matches: the lower, the better.
  var RANK_TITLE = 0;
  var RANK_TITLES = 1;
  var RANK_ARTIST = 2;
  var RANK_PHRASE = 3; // the words together in one line of the lyrics
  var RANK_LYRICS = 4; // the words in the lyrics, apart

  var form = document.querySelector(".search");
  if (!form) {
    return;
  }
  var field = form.querySelector(".search-field");
  var status = document.querySelector(".search-status");
  var resultList = document.querySelector(".search-results");
  var indexUrl = form.dataset.indexUrl;
  var songbookPath = form.dataset.songbookPath;

  var songs = null; // the prepared index, once loaded
  var loading = null; // the request for it, while loading

  /* "Čerešně" and "ceresne" are the same word. */
  function fold(text) {
    return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  }

  function prepare(entries) {
    return entries.map(function (entry) {
      var lines = entry.lyrics.split("\n");
      return {
        entry: entry,
        lines: lines,
        title: fold(entry.title),
        titles: fold([entry.title].concat(entry.altTitles).join("\n")),
        artists: fold(entry.artists.join("\n")),
        foldedLines: lines.map(fold)
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

  function containsAll(text, words) {
    return words.every(function (word) {
      return text.indexOf(word) !== -1;
    });
  }

  /* The rank of a song for these words, or null if it does not match. */
  function rank(song, words) {
    if (containsAll(song.title, words)) {
      return RANK_TITLE;
    }
    if (containsAll(song.titles, words)) {
      return RANK_TITLES;
    }
    if (containsAll(song.titles + "\n" + song.artists, words)) {
      return RANK_ARTIST;
    }
    var everything = song.titles + "\n" + song.artists + "\n" + song.foldedLines.join("\n");
    if (!containsAll(everything, words)) {
      return null;
    }
    return lineIndexOf(song, words.join(" ")) !== -1 ? RANK_PHRASE : RANK_LYRICS;
  }

  function search(words) {
    var found = [];
    songs.forEach(function (song, position) {
      var songRank = rank(song, words);
      if (songRank !== null) {
        found.push({ song: song, rank: songRank, position: position });
      }
    });
    return found.sort(function (a, b) {
      return a.rank - b.rank || a.position - b.position;
    });
  }

  /* The first line of the lyrics with this text, or -1. */
  function lineIndexOf(song, text) {
    return song.foldedLines.findIndex(function (line) { return line.indexOf(text) !== -1; });
  }

  /* The line of the lyrics that shows why a song was found: the one with all
     the words, else the first with one of them. */
  function matchingLine(song, words) {
    var index = lineIndexOf(song, words.join(" "));
    for (var i = 0; index === -1 && i < words.length; i += 1) {
      index = lineIndexOf(song, words[i]);
    }
    return index === -1 ? null : song.lines[index];
  }

  /* An other title of the song with one of the words. */
  function matchingOtherTitle(song, words) {
    var found = song.entry.altTitles.filter(function (title) {
      var folded = fold(title);
      return words.some(function (word) { return folded.indexOf(word) !== -1; });
    });
    return found.length ? found[0] : null;
  }

  function element(tag, className, text) {
    var created = document.createElement(tag);
    created.className = className;
    created.textContent = text;
    return created;
  }

  function resultItem(match, words) {
    var entry = match.song.entry;
    var item = document.createElement("li");
    var link = document.createElement("a");
    link.href = songbookPath + entry.id + "/";
    link.appendChild(element("span", "result-title", entry.title));
    item.appendChild(link);
    if (entry.artists.length) {
      item.appendChild(element("span", "result-artists", entry.artists.join(" · ")));
    }
    var otherTitle = matchingOtherTitle(match.song, words);
    if (otherTitle) {
      item.appendChild(element("span", "result-detail", "též: " + otherTitle));
    }
    if (match.rank >= RANK_PHRASE) {
      var line = matchingLine(match.song, words);
      if (line) {
        item.appendChild(element("span", "result-detail result-line", line));
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

  function showResults(found, words) {
    resultList.replaceChildren.apply(
      resultList,
      found.slice(0, MAX_RESULTS).map(function (match) { return resultItem(match, words); })
    );
    if (found.length === 0) {
      showStatus("Nic nenalezeno.");
    } else if (found.length > MAX_RESULTS) {
      showStatus(countText(found.length) + ", zobrazeno prvních " + MAX_RESULTS + ". Upřesněte hledání.");
    } else {
      showStatus(countText(found.length));
    }
  }

  function clearResults() {
    resultList.replaceChildren();
  }

  function splitWords(query) {
    return fold(query).split(/\s+/).filter(Boolean);
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
