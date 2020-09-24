/*
 * Timer.h
 *
 *  Created on: Sep 2, 2020
 *      Author: Ali Kheradmand (kheradm2@illinois.edu)
 */

#ifndef TIMER_H_
#define TIMER_H_

#include <chrono>
#include <iostream>
#include <iomanip>

struct Timer {
    std::chrono::time_point<std::chrono::high_resolution_clock> start;

    Timer() {
        reset();
    }

    void reset() {
        start = std::chrono::high_resolution_clock::now();
    }

    double elapsed() const {
        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> diff = end-start;
        return diff.count();
    }
};

std::ostream& operator<<(std::ostream& out, const Timer& timer) {
    out << std::setprecision(2) << timer.elapsed() << " s";
    return out;
}




#endif /* TIMER_H_ */
