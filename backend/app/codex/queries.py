PREDICTION_CATEGORIES = """
query PredictionCategories {
  predictionCategories {
    name
    slug
    subcategories {
      name
      slug
      subcategories {
        name
        slug
      }
    }
  }
}
"""

DISCOVER_EVENTS = """
query DiscoverEvents($categories: [String!], $limit: Int!, $offset: Int!) {
  filterPredictionEvents(
    filters: {
      protocol: [POLYMARKET, KALSHI]
      status: [OPEN]
      categories: $categories
    }
    rankings: [{ attribute: relevanceScore24h, direction: DESC }]
    limit: $limit
    offset: $offset
  ) {
    count
    page
    results {
      id
      status
      categories
      marketCount
      trendingScore24h
      relevanceScore24h
      liquidityUsd
      openInterestUsd
      volumeUsd24h
      trades24h
      uniqueTraders24h
      event {
        id
        protocol
        status
        slug
        question
        description
        imageThumbUrl
        venueUrl
        closesAt
        resolvesAt
      }
      markets {
        id
        label
      }
    }
  }
}
"""

EVENT_MARKETS = """
query EventMarkets($eventIds: [String!], $limit: Int!) {
  filterPredictionMarkets(
    eventIds: $eventIds
    rankings: [{ attribute: openInterestUsd, direction: DESC }]
    limit: $limit
  ) {
    count
    results {
      id
      eventLabel
      status
      market {
        id
        eventId
        protocol
        label
        question
        imageThumbUrl
        status
        closesAt
        resolvesAt
      }
      outcome0 {
        label
        bestAskCT
        bestBidCT
        spreadCT
        lastPriceCT
        liquidityCT
        volumeUsd24h
        priceChange24h
      }
      outcome1 {
        label
        bestAskCT
        bestBidCT
        spreadCT
        lastPriceCT
        liquidityCT
        volumeUsd24h
        priceChange24h
      }
      competitiveScore24h
      trendingScore24h
      liquidityUsd
      openInterestUsd
      volumeUsd24h
      trades24h
      priceCompetitiveness
    }
  }
}
"""

MARKET_BARS = """
query PredictionMarketBars($marketId: String!, $from: Int!, $to: Int!, $resolution: String!) {
  predictionMarketBars(
    input: {
      marketId: $marketId
      from: $from
      to: $to
      resolution: $resolution
      removeEmptyBars: true
    }
  ) {
    marketId
    predictionMarket {
      id
      label
      question
      outcomeLabels
      eventLabel
    }
    bars {
      t
      volumeUsd
      trades
      uniqueTraders
      openInterestUsd { o h l c }
      outcome0 {
        volumeUsd
        priceCollateralToken { o h l c }
        bidCollateralToken { o h l c }
        askCollateralToken { o h l c }
      }
      outcome1 {
        volumeUsd
        priceCollateralToken { o h l c }
        bidCollateralToken { o h l c }
        askCollateralToken { o h l c }
      }
    }
  }
}
"""

