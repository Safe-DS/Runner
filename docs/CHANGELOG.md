## [0.17.0](https://github.com/Safe-DS/Runner/compare/v0.16.0...v0.17.0) (2024-05-29)


### Features

* require `safe-ds` version 0.26.0  ([#119](https://github.com/Safe-DS/Runner/issues/119)) ([1360d9a](https://github.com/Safe-DS/Runner/commit/1360d9a6647fc9e342be5c427a5181114f087467))


### Bug Fixes

* catch possible pickling errors ([#118](https://github.com/Safe-DS/Runner/issues/118)) ([6333b64](https://github.com/Safe-DS/Runner/commit/6333b643490909703f53025698f0045912dd8c38))

## [0.16.0](https://github.com/Safe-DS/Runner/compare/v0.15.0...v0.16.0) (2024-05-15)


### Features

* require `safe-ds` version 0.25.0 ([#114](https://github.com/Safe-DS/Runner/issues/114)) ([69680de](https://github.com/Safe-DS/Runner/commit/69680de2c310dfba177d581926d70619925fcf00))

## [0.15.0](https://github.com/Safe-DS/Runner/compare/v0.14.1...v0.15.0) (2024-05-09)


### Features

* require `safe-ds` version 0.24.0 ([#112](https://github.com/Safe-DS/Runner/issues/112)) ([7236941](https://github.com/Safe-DS/Runner/commit/7236941ba8842c59d48c14f753d78458ef387c88))


### Bug Fixes

* **deps:** bump jinja2 from 3.1.3 to 3.1.4 ([#111](https://github.com/Safe-DS/Runner/issues/111)) ([2866863](https://github.com/Safe-DS/Runner/commit/2866863b3aa68cb224435afacd2e2d0ec11ad4cd))

## [0.14.1](https://github.com/Safe-DS/Runner/compare/v0.14.0...v0.14.1) (2024-05-02)


### Bug Fixes

* require `safe-ds` version 0.22.1 ([#105](https://github.com/Safe-DS/Runner/issues/105)) ([f3eeabe](https://github.com/Safe-DS/Runner/commit/f3eeabeb5497740cea7a9cd1d001957bc3e76c9b))

## [0.14.0](https://github.com/Safe-DS/Runner/compare/v0.13.1...v0.14.0) (2024-05-02)


### Features

* require `safe-ds` version 0.22.0 ([#98](https://github.com/Safe-DS/Runner/issues/98)) ([6f7c934](https://github.com/Safe-DS/Runner/commit/6f7c934ae200d8dd41f6e135f24469302c8490c8))

## [0.13.1](https://github.com/Safe-DS/Runner/compare/v0.13.0...v0.13.1) (2024-04-24)


### Bug Fixes

* possible attribute error when adding `__ex_id__` ([#96](https://github.com/Safe-DS/Runner/issues/96)) ([7cfc0e2](https://github.com/Safe-DS/Runner/commit/7cfc0e2b62821cf6a78cec40004a59ee0e68326e)), closes [#93](https://github.com/Safe-DS/Runner/issues/93)

## [0.13.0](https://github.com/Safe-DS/Runner/compare/v0.12.0...v0.13.0) (2024-04-24)


### Features

* pass keyword arguments separately in memoized calls ([#95](https://github.com/Safe-DS/Runner/issues/95)) ([0f63b0c](https://github.com/Safe-DS/Runner/commit/0f63b0c17e03b769158024d339d656e2d8ee306c))

## [0.12.0](https://github.com/Safe-DS/Runner/compare/v0.11.0...v0.12.0) (2024-04-22)


### Features

* handle list of filenames in `absolute_path` and `file_mtime` ([#89](https://github.com/Safe-DS/Runner/issues/89)) ([50d831f](https://github.com/Safe-DS/Runner/commit/50d831fb2ed5381e4d4f5bf291431dcf3b7edd07)), closes [#88](https://github.com/Safe-DS/Runner/issues/88)
* prepare and pool processes ([#87](https://github.com/Safe-DS/Runner/issues/87)) ([e5e7011](https://github.com/Safe-DS/Runner/commit/e5e7011eca50a49acd7f8c0ca937ad43faf393e6)), closes [#85](https://github.com/Safe-DS/Runner/issues/85)

## [0.11.0](https://github.com/Safe-DS/Runner/compare/v0.10.0...v0.11.0) (2024-04-17)


### Features

* bump `safe-ds` to `v0.21.0` ([#86](https://github.com/Safe-DS/Runner/issues/86)) ([d780822](https://github.com/Safe-DS/Runner/commit/d78082222d179d61a53ec9a3560246aad2f74c32)), closes [#85](https://github.com/Safe-DS/Runner/issues/85)
* memoization improvements ([#81](https://github.com/Safe-DS/Runner/issues/81)) ([6bc2288](https://github.com/Safe-DS/Runner/commit/6bc22889afc8e61922cb2905badad2974cff9b54)), closes [#44](https://github.com/Safe-DS/Runner/issues/44)

## [0.10.0](https://github.com/Safe-DS/Runner/compare/v0.9.0...v0.10.0) (2024-04-10)


### Features

* support relative paths ([#83](https://github.com/Safe-DS/Runner/issues/83)) ([a65261b](https://github.com/Safe-DS/Runner/commit/a65261b5b1e71c1949a6feb352d9ea435952a3e6)), closes [#76](https://github.com/Safe-DS/Runner/issues/76)

## [0.9.0](https://github.com/Safe-DS/Runner/compare/v0.8.0...v0.9.0) (2024-04-09)


### Features

* dynamic memoization calls ([#82](https://github.com/Safe-DS/Runner/issues/82)) ([9d31292](https://github.com/Safe-DS/Runner/commit/9d31292f4eae69bb65a6c6f4b7a8bddade89cc32))


### Bug Fixes

* **deps:** bump pillow from 10.2.0 to 10.3.0 ([#77](https://github.com/Safe-DS/Runner/issues/77)) ([32974d0](https://github.com/Safe-DS/Runner/commit/32974d07acd9cc121fa4d6980c2814c9ec8d6787))
* more robust hashing & pickling when memoizing ([#80](https://github.com/Safe-DS/Runner/issues/80)) ([25c49e2](https://github.com/Safe-DS/Runner/commit/25c49e29da2506d514485b001dd8fc27caf230f9)), closes [#75](https://github.com/Safe-DS/Runner/issues/75) [#79](https://github.com/Safe-DS/Runner/issues/79)

## [0.8.0](https://github.com/Safe-DS/Runner/compare/v0.7.0...v0.8.0) (2024-04-03)


### Features

* **deps:** bump safe-ds from 0.19.0 to 0.20.0 ([#74](https://github.com/Safe-DS/Runner/issues/74)) ([86cccff](https://github.com/Safe-DS/Runner/commit/86cccff7d2230075eccc443d3bd55b31d2816bb5))


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
