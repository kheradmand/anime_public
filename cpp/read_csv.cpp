/*
 * read_csv.cpp
 *
 *  Created on: Sep 17, 2020
 *      Author: ali
 */

#ifndef READ_CSV_CPP_
#define READ_CSV_CPP_

#include <iostream>
#include <sstream>
using namespace std;

int main(int argc, char** argv){
    int k;
    double tp,pp,ap;
    char c;
    int i = 0;
    assert(argc > 1);
    stringstream ss{argv[1]};
    double thresh;
    ss >> thresh;
    cout << "threshold is " << thresh << endl;
    while (true){
        if (i == 0){
            string temp;
            getline(cin, temp);
            i++;
            continue;
        }
        cin >> k;
        cin >> c;
        assert(c == ',');
        cin >> tp;
        cin >> c;
        assert(c == ',');
        cin >> pp;
        cin >> c;
        assert(c == ',');
        cin >> ap;
        //cout << k << "," << tp << "," << pp <<"," << ap << endl;
        if (tp/pp < thresh){
            cout << i << "  " << k << " " << tp << " " << pp << " " << ap << " " << " pr:" << (tp/ap) << endl;
            return 0;
        }
        i++;
    }
    return 0;
}

#endif /* READ_CSV_CPP_ */
