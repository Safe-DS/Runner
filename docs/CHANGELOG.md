## [0.8.0](https://github.com/Safe-DS/Runner/compare/v0.7.0...v0.8.0) (2024-04-03)


### Features

* **deps:** bump safe-ds from 0.19.0 to 0.20.0 ([#74](https://github.com/Safe-DS/Runner/issues/74)) ([86cccff](https://github.com/Safe-DS/Runner/commit/86cccff7d2230075eccc443d3bd55b31d2816bb5)), closes [#573](https://github.com/Safe-DS/Runner/issues/573) [#529](https://github.com/Safe-DS/Runner/issues/529) [#522](https://github.com/Safe-DS/Runner/issues/522) [#588](https://github.com/Safe-DS/Runner/issues/588) [#548](https://github.com/Safe-DS/Runner/issues/548) [#519](https://github.com/Safe-DS/Runner/issues/519) [#550](https://github.com/Safe-DS/Runner/issues/550) [#549](https://github.com/Safe-DS/Runner/issues/549) [#572](https://github.com/Safe-DS/Runner/issues/572) [#571](https://github.com/Safe-DS/Runner/issues/571) [#567](https://github.com/Safe-DS/Runner/issues/567) [#587](https://github.com/Safe-DS/Runner/issues/587) [#582](https://github.com/Safe-DS/Runner/issues/582) [#585](https://github.com/Safe-DS/Runner/issues/585) [#573](https://github.com/Safe-DS/Runner/issues/573) [#529](https://github.com/Safe-DS/Runner/issues/529) [#522](https://github.com/Safe-DS/Runner/issues/522) [#588](https://github.com/Safe-DS/Runner/issues/588) [#548](https://github.com/Safe-DS/Runner/issues/548) [#519](https://github.com/Safe-DS/Runner/issues/519) [#550](https://github.com/Safe-DS/Runner/issues/550) [#549](https://github.com/Safe-DS/Runner/issues/549) [#572](https://github.com/Safe-DS/Runner/issues/572) [#571](https://github.com/Safe-DS/Runner/issues/571) [#567](https://github.com/Safe-DS/Runner/issues/567) [#587](https://github.com/Safe-DS/Runner/issues/587) [#582](https://github.com/Safe-DS/Runner/issues/582) [#585](https://github.com/Safe-DS/Runner/issues/585) [#605](https://github.com/Safe-DS/Runner/issues/605) [#604](https://github.com/Safe-DS/Runner/issues/604) [#603](https://github.com/Safe-DS/Runner/issues/603) [#593](https://github.com/Safe-DS/Runner/issues/593) [#598](https://github.com/Safe-DS/Runner/issues/598) [#595](https://github.com/Safe-DS/Runner/issues/595) [#594](https://github.com/Safe-DS/Runner/issues/594) [#591](https://github.com/Safe-DS/Runner/issues/591) [#590](https://github.com/Safe-DS/Runner/issues/590)


### Bug Fixes

* sending images to the vscode extension fails, if the tensor is not local to the cpu ([#63](https://github.com/Safe-DS/Runner/issues/63)) ([8cf0b57](https://github.com/Safe-DS/Runner/commit/8cf0b5702eedec1cadd2225e6665f4cdcb69b6f8))


### Performance Improvements

* faster startup ([#55](https://github.com/Safe-DS/Runner/issues/55)) ([a3fbe24](https://github.com/Safe-DS/Runner/commit/a3fbe24769254d9180c84e5085685113e49a7f6a))

## [0.7.0](https://github.com/Safe-DS/Runner/compare/v0.6.0...v0.7.0) (2024-02-22)


### Features

* cleaner public api ([#54](https://github.com/Safe-DS/Runner/issues/54)) ([6d8dde7](https://github.com/Safe-DS/Runner/commit/6d8dde746729ff40ad0df4a548e7d607afe27f5c)), closes [#53](https://github.com/Safe-DS/Runner/issues/53)

## [0.6.0](https://github.com/Safe-DS/Runner/compare/v0.5.0...v0.6.0) (2024-02-08)


### Features

* track memoization stats ([#51](https://github.com/Safe-DS/Runner/issues/51)) ([50f30a3](https://github.com/Safe-DS/Runner/commit/50f30a36cf5579f74605992c4e80fd2f6f7f5d7d)), closes [#44](https://github.com/Safe-DS/Runner/issues/44)

## [0.5.0](https://github.com/Safe-DS/Runner/compare/v0.4.0...v0.5.0) (2024-01-26)


### Features

* added json serializer that encodes tables and images ([#29](https://github.com/Safe-DS/Runner/issues/29)) ([054cca4](https://github.com/Safe-DS/Runner/commit/054cca4cf8025932c0a73e1f734a31fb20cab99a)), closes [#20](https://github.com/Safe-DS/Runner/issues/20)
* Memoization ([#38](https://github.com/Safe-DS/Runner/issues/38)) ([2a26b48](https://github.com/Safe-DS/Runner/commit/2a26b48405225516e550703f3f9cdce49079eaae))
* Replace flask with quart ([#43](https://github.com/Safe-DS/Runner/issues/43)) ([5520b68](https://github.com/Safe-DS/Runner/commit/5520b68143795609513e63def569cdbec0e6df6a)), closes [#42](https://github.com/Safe-DS/Runner/issues/42)
* support placeholder queries that only request a subset of data ([#39](https://github.com/Safe-DS/Runner/issues/39)) ([dae57dc](https://github.com/Safe-DS/Runner/commit/dae57dc93134cfe5e1ec0d1e5120c66aaf77f085))
* update to safe-ds 0.17.1 + server refactor ([#37](https://github.com/Safe-DS/Runner/issues/37)) ([1bcad07](https://github.com/Safe-DS/Runner/commit/1bcad07fdbea1051a4334029e64dc5b4cf7e0ba0))


### Bug Fixes

* allow multiple connections to work with the runner ([#31](https://github.com/Safe-DS/Runner/issues/31)) ([64685a3](https://github.com/Safe-DS/Runner/commit/64685a36840dc5785e756a27d1b3c2396e71e47b))

## [0.4.0](https://github.com/Safe-DS/Runner/compare/v0.3.0...v0.4.0) (2023-12-05)


### Features

* shutdown messages ([#25](https://github.com/Safe-DS/Runner/issues/25)) ([93fcb85](https://github.com/Safe-DS/Runner/commit/93fcb85de9adff9b4206627447ad79347c43dfaa)), closes [#24](https://github.com/Safe-DS/Runner/issues/24)


### Bug Fixes

* race condition when initializing multiprocessing manager ([#26](https://github.com/Safe-DS/Runner/issues/26)) ([fc5934f](https://github.com/Safe-DS/Runner/commit/fc5934f7ad1c5d91aedb439a0f91396d519afd2b)), closes [#18](https://github.com/Safe-DS/Runner/issues/18)

## [0.3.0](https://github.com/Safe-DS/Runner/compare/v0.2.1...v0.3.0) (2023-12-04)


### Features

* add cli argument to display runner version ([#21](https://github.com/Safe-DS/Runner/issues/21)) ([3917c5f](https://github.com/Safe-DS/Runner/commit/3917c5f7491711367c872d907800e869de255cd8)), closes [#19](https://github.com/Safe-DS/Runner/issues/19)

## [0.2.1](https://github.com/Safe-DS/Runner/compare/v0.2.0...v0.2.1) (2023-11-30)


### Bug Fixes

* add missing launch script ([#16](https://github.com/Safe-DS/Runner/issues/16)) ([1564add](https://github.com/Safe-DS/Runner/commit/1564add6f868869297f39151499f174c47750f8d))
* runner startup crash ([#15](https://github.com/Safe-DS/Runner/issues/15)) ([01df889](https://github.com/Safe-DS/Runner/commit/01df8891985b240ebd1ed2f1560f0cdacb1f6a55))

## [0.2.0](https://github.com/Safe-DS/Runner/compare/v0.1.0...v0.2.0) (2023-11-30)


### Features

* python server ([#6](https://github.com/Safe-DS/Runner/issues/6)) ([a2c4f0f](https://github.com/Safe-DS/Runner/commit/a2c4f0f1d0cd084bce47e4baf888ef50bf2e22df))

## [0.1.0](https://github.com/Safe-DS/Runner/compare/v0.0.1...v0.1.0) (2023-11-29)


### Features

* drop Python 3.10 and add Python 3.12 ([#4](https://github.com/Safe-DS/Runner/issues/4)) ([08a8972](https://github.com/Safe-DS/Runner/commit/08a8972af06a3ee26a6da4b133403e5e78933185))
